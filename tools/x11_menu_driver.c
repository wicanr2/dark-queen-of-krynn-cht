/* DRAFT GUI 驗證：只透過 X11 鍵盤事件操作視窗，不呼叫 Oracle 或寫遊戲狀態。 */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
static char status_path[4096];
static const char *count_field="inputs";

static Window find_window(Display *d, Window w, unsigned long pid) {
    Atom type; int format; unsigned long n, extra; unsigned char *data = NULL;
    XGetWindowProperty(d,w,XInternAtom(d,"_NET_WM_PID",False),0,1,False,AnyPropertyType,
                       &type,&format,&n,&extra,&data);
    int matches = data && format==32 && n==1 && *(unsigned long *)data==pid;
    if(data) XFree(data);
    if(matches) return w;
    Window root,parent,*children=NULL; unsigned int count=0;
    if(!XQueryTree(d,w,&root,&parent,&children,&count)) return 0;
    Window found=0;
    for(unsigned int i=0;i<count && !found;i++) found=find_window(d,children[i],pid);
    if(children) XFree(children);
    return found;
}
static unsigned long long number(const char *json,const char *key) {
    char needle[80]; snprintf(needle,sizeof needle,"\"%s\":",key);
    const char *p=strstr(json,needle); return p?strtoull(p+strlen(needle),NULL,10):0;
}
static unsigned long long input_count(void) {
    char json[8192];FILE *f=fopen(status_path,"r");if(!f)return 0;
    size_t n=fread(json,1,sizeof json-1,f);json[n]=0;fclose(f);return number(json,count_field);
}
static void send_key(Display *d,Window w,KeySym sym) {
    unsigned long long before=input_count();
    XSetInputFocus(d,w,RevertToParent,CurrentTime);
    XKeyEvent e={0};e.display=d;e.window=w;e.root=DefaultRootWindow(d);e.same_screen=True;
    e.keycode=XKeysymToKeycode(d,sym);e.type=KeyPress;
    if(!e.keycode || !XSendEvent(d,w,False,KeyPressMask,(XEvent *)&e)) exit(3);
    XFlush(d);
    struct timespec start,now,pause={0,5000000};clock_gettime(CLOCK_MONOTONIC,&start);
    while(input_count()==before) {
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-start.tv_sec>3) {fprintf(stderr,"X11 key not accepted\n");exit(3);}
        nanosleep(&pause,NULL);
    }
    e.type=KeyRelease;XSendEvent(d,w,False,KeyReleaseMask,(XEvent *)&e);XFlush(d);
}
static unsigned char component(unsigned long pixel,unsigned long mask) {
    unsigned int shift=0;while(mask && !(mask&1)){mask>>=1;shift++;}
    return mask?(unsigned char)((((pixel>>shift)&mask)*255)/mask):0;
}
static void capture(Display *d,Window w,const char *directory,const char *status) {
    XWindowAttributes a;if(!XGetWindowAttributes(d,w,&a)) exit(6);
    XImage *im=XGetImage(d,w,0,0,(unsigned int)a.width,(unsigned int)a.height,AllPlanes,ZPixmap);
    if(!im) exit(6);
    char path[4096];snprintf(path,sizeof path,"%s/actual-window.ppm",directory);
    FILE *f=fopen(path,"wb");if(!f) exit(6);fprintf(f,"P6\n%d %d\n255\n",a.width,a.height);
    for(int y=0;y<a.height;y++)for(int x=0;x<a.width;x++){
        unsigned long p=XGetPixel(im,x,y);
        unsigned char rgb[3]={component(p,im->red_mask),component(p,im->green_mask),component(p,im->blue_mask)};
        if(fwrite(rgb,1,3,f)!=3) exit(6);
    }
    fclose(f);XDestroyImage(im);
    snprintf(path,sizeof path,"%s/x11-capture.json",directory);f=fopen(path,"w");if(!f)exit(6);
    fprintf(f,"{\"width\":%d,\"height\":%d,\"window\":%lu,\"step\":%llu}\n",a.width,a.height,w,number(status,"step"));fclose(f);
}
/* 閱讀元件停在原版完整畫面；本段只送 X11 事件及擷取視窗。 */
static void reader_status(char *json,size_t capacity) {
    FILE *f=fopen(status_path,"r");json[0]=0;if(!f)return;
    size_t n=fread(json,1,capacity-1,f);json[n]=0;fclose(f);
}
static int reader_test(Display *d,unsigned long pid,const char *directory,int long_page) {
    Window w=0;char json[8192],subdir[4096],path[4096];
    struct timespec start,now,pause={0,10000000};clock_gettime(CLOCK_MONOTONIC,&start);
    for(;;) {
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-start.tv_sec>150) {fprintf(stderr,"reader X11 readiness timeout\n");return 4;}
        if(!w)w=find_window(d,DefaultRootWindow(d),pid);
        reader_status(json,sizeof json);
        if(w && number(json,"step")==810000000ULL && number(json,"reader_entry")== (long_page?50:54) &&
           strstr(json,"\"reader_stable\":true") &&
           strstr(json,long_page?"\"reader_mode\":\"probe\"":"\"reader_mode\":\"browse\""))break;
        nanosleep(&pause,NULL);
    }
    count_field="reader_inputs";
    /* latest.json 在 Draw 內寫出；X11 實際呈現要等 Draw 返回後完成。 */
    struct timespec present={0,80000000};nanosleep(&present,NULL);XSync(d,False);
    KeySym long_keys[]={XK_Page_Down,XK_Page_Down,XK_Page_Up,XK_Page_Down,XK_Escape};
    KeySym seen_keys[]={XK_Left,XK_Right,XK_Page_Down,XK_F5};
    unsigned int pages[]={1,2,2,1,2};
    int count=long_page?5:4;
    for(int phase=0;phase<count;phase++) {
        reader_status(json,sizeof json);
        if(number(json,"step")!=810000000ULL || number(json,"reader_page")!=(long_page?pages[phase]:1) ||
           number(json,"reader_entry")!=(long_page?50:54))return 7;
        snprintf(subdir,sizeof subdir,"%s/reader-%d",directory,phase);
        if(mkdir(subdir,0755))return 6;
        capture(d,w,subdir,json);
        snprintf(path,sizeof path,"%s/latest.json",subdir);
        FILE *f=fopen(path,"w");if(!f)return 6;fputs(json,f);fclose(f);
        send_key(d,w,long_page?long_keys[phase]:seen_keys[phase]);
        struct timespec release={0,80000000};nanosleep(&release,NULL);
    }
    return 0;
}
static int reader_image_test(Display *d,unsigned long pid,const char *directory) {
    Window w=0;char json[8192],subdir[4096],path[4096];
    struct timespec start,now,pause={0,10000000},present={0,80000000};
    clock_gettime(CLOCK_MONOTONIC,&start);
    for(;;) {
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-start.tv_sec>150)return 4;
        if(!w)w=find_window(d,DefaultRootWindow(d),pid);
        reader_status(json,sizeof json);
        if(w && number(json,"step")==810000000ULL && number(json,"reader_entry")==64 &&
           strstr(json,"\"reader_stable\":true") && strstr(json,"\"reader_mode\":\"probe\""))break;
        nanosleep(&pause,NULL);
    }
    count_field="reader_inputs";
    KeySym keys[]={XK_equal,XK_s,XK_d,XK_equal,XK_minus,XK_Home,XK_Escape};
    for(int phase=0;phase<7;phase++) {
        nanosleep(&present,NULL);XSync(d,False);
        reader_status(json,sizeof json);
        if(number(json,"step")!=810000000ULL || number(json,"reader_entry")!=64 ||
           number(json,"reader_page")!=1 || !strstr(json,"\"reader_mode\":\"probe\""))return 7;
        snprintf(subdir,sizeof subdir,"%s/reader-%d",directory,phase);
        if(mkdir(subdir,0755))return 6;
        capture(d,w,subdir,json);
        snprintf(path,sizeof path,"%s/latest.json",subdir);
        FILE *f=fopen(path,"w");if(!f)return 6;fputs(json,f);fclose(f);
        send_key(d,w,keys[phase]);nanosleep(&present,NULL);
    }
    return 0;
}
int main(int argc,char **argv) {
    if(argc!=4) {fprintf(stderr,"usage: driver pid output roundtrip|adventure\n");return 2;}
    int adventure=!strcmp(argv[3],"adventure");
    int image_reader=!strcmp(argv[3],"reader-image");
    int reader=!strcmp(argv[3],"reader-long") || !strcmp(argv[3],"reader-seen") || image_reader;
    if(!adventure && strcmp(argv[3],"roundtrip") && !reader) return 2;
    Display *d=XOpenDisplay(NULL);if(!d) return 2;
    unsigned long pid=strtoul(argv[1],NULL,10); Window w=0;
    char path[4096],json[8192];snprintf(path,sizeof path,"%s/latest.json",argv[2]);
    snprintf(status_path,sizeof status_path,"%s/latest.json",argv[2]);
    if(reader) {
        int result=image_reader?reader_image_test(d,pid,argv[2]):reader_test(d,pid,argv[2],!strcmp(argv[3],"reader-long"));
        XCloseDisplay(d);return result;
    }
    int phase=0,spaces=0; unsigned long long previous_send=0;
    struct timespec start,now,pause={0,10000000};clock_gettime(CLOCK_MONOTONIC,&start);
    for(;;) {
        clock_gettime(CLOCK_MONOTONIC,&now);if(now.tv_sec-start.tv_sec>150) {fprintf(stderr,"X11 driver timeout phase=%d spaces=%d\n",phase,spaces);return 4;}
        if(!w) w=find_window(d,DefaultRootWindow(d),pid);
        FILE *f=fopen(path,"r");if(!f || !w) {if(f)fclose(f);nanosleep(&pause,NULL);continue;}
        size_t len=fread(json,1,sizeof json-1,f);json[len]=0;fclose(f);
        unsigned long long step=number(json,"step"),active=number(json,"active"),consumed=number(json,"keys_consumed");
        int held=strstr(json,"\"held\":true")!=NULL;
        if(spaces<7 && step>=101000000ULL+spaces*20000000ULL) {
            send_key(d,w,XK_space);spaces++;previous_send=step;
        } else if(spaces==7 && phase==0 && step>=241000000ULL) {
            send_key(d,w,XK_p);phase=1;previous_send=step;
        } else if(phase==1 && active==12 && !held && consumed>=8 && step>previous_send+3000000ULL) {
            send_key(d,w,XK_l);phase=2;previous_send=step;
        } else if(phase==2 && active==0 && !held && consumed>=9 && step>previous_send+3000000ULL) {
            send_key(d,w,adventure?XK_t:XK_e);phase=3;previous_send=step;
        } else if(phase==3 && !adventure && active==12 && !held && consumed>=10 && step>previous_send+3000000ULL) {
            break;
        } else if(phase==3 && adventure && active==0 && !held && consumed>=10 && step>previous_send+3000000ULL) {
            send_key(d,w,XK_a);phase=4;previous_send=step;
        } else if(phase==4 && active==12 && !held && consumed>=11 && step>previous_send+3000000ULL) {
            send_key(d,w,XK_b);phase=5;previous_send=step;
        } else if(phase==5 && active==0 && !held && consumed>=12 && step>previous_send+10000000ULL) {
            send_key(d,w,XK_x);phase=6;previous_send=step;
        } else if(phase==6 && consumed>=13 && step>previous_send+2000000ULL) {
            send_key(d,w,XK_BackSpace);phase=7;previous_send=step;
        } else if(phase==7 && consumed>=14 && step>previous_send+2000000ULL) {
            break;
        }
        nanosleep(&pause,NULL);
    }
    capture(d,w,argv[2],json);
    XEvent close_event={0};close_event.xclient.type=ClientMessage;close_event.xclient.window=w;
    close_event.xclient.message_type=XInternAtom(d,"WM_PROTOCOLS",False);close_event.xclient.format=32;
    close_event.xclient.data.l[0]=(long)XInternAtom(d,"WM_DELETE_WINDOW",False);close_event.xclient.data.l[1]=CurrentTime;
    if(!XSendEvent(d,w,False,NoEventMask,&close_event)) return 5;
    XFlush(d);
    XCloseDisplay(d);return 0;
}
