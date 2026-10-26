/* 正常玩家視窗的有界抽樣。只送 X11 鍵盤與正常關窗訊息，不修改遊戲狀態。 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
#include <sys/wait.h>

static char key_helper[4096];
static void fake_key(unsigned code,const char *state) {
    char text[16];snprintf(text,sizeof(text),"%u",code);
    pid_t child=fork();if(child<0)exit(12);
    if(child==0){execl(key_helper,key_helper,text,state,(char*)NULL);_exit(12);}
    int status;if(waitpid(child,&status,0)<0||!WIFEXITED(status)||WEXITSTATUS(status))exit(12);
}

static Window find_window(Display *d, Window root) {
    Window parent,actual,*children=NULL,result=0;unsigned n=0;
    char *name=NULL;
    if(XFetchName(d,root,&name)&&name){if(strstr(name,"黑暗之后"))result=root;XFree(name);}
    if(!result){
        Atom type;int format;unsigned long count,remaining;unsigned char *data=NULL;
        if(XGetWindowProperty(d,root,XInternAtom(d,"_NET_WM_NAME",False),0,1024,False,AnyPropertyType,&type,&format,&count,&remaining,&data)==Success&&data){
            if(strstr((char*)data,"黑暗之后"))result=root;
            XFree(data);
        }
    }
    if(!result&&root!=DefaultRootWindow(d)){
        XWindowAttributes a;
        if(XGetWindowAttributes(d,root,&a)&&a.map_state==IsViewable&&a.width>=640&&a.height>=400)result=root;
    }
    if(result)return result;
    if(XQueryTree(d,root,&actual,&parent,&children,&n)){
        for(unsigned i=0;i<n&&!result;i++)result=find_window(d,children[i]);
        if(children)XFree(children);
    }
    return result;
}
static void key(Display *d,Window w,KeySym sym) {
    XSetInputFocus(d,w,RevertToParent,CurrentTime);
    XSync(d,False);unsigned code=XKeysymToKeycode(d,sym);
    fake_key(code,"down");usleep(3000000);fake_key(code,"up");
}
static unsigned component(unsigned long pixel,unsigned long mask) {
    if(!mask)return 0;
    unsigned shift=0;while(!(mask&1)){mask>>=1;shift++;}
    return (unsigned)(((pixel>>shift)&mask)*255/mask);
}
static void capture(Display *d,Window w,const char *directory,const char *name) {
    XWindowAttributes a;if(!XGetWindowAttributes(d,w,&a))exit(3);
    XImage *im=XGetImage(d,w,0,0,a.width,a.height,AllPlanes,ZPixmap);if(!im)exit(4);
    char path[4096];snprintf(path,sizeof(path),"%s/%s.ppm",directory,name);
    FILE *f=fopen(path,"wb");if(!f)exit(5);fprintf(f,"P6\n%d %d\n255\n",a.width,a.height);
    for(int y=0;y<a.height;y++)for(int x=0;x<a.width;x++){
        unsigned long p=XGetPixel(im,x,y);unsigned char rgb[3]={component(p,im->red_mask),component(p,im->green_mask),component(p,im->blue_mask)};fwrite(rgb,1,3,f);
    }
    fclose(f);XDestroyImage(im);
}
/* 等實際完整介面，避免固定秒數在較忙的容器裡提前送出下一個按鍵。 */
static int wait_reference(Display *d,Window w,const char *directory,const char *name) {
    char path[4096],magic[3];int width,height,max;
    snprintf(path,sizeof(path),"%s/%s.ppm",directory,name);
    FILE *f=fopen(path,"rb");if(!f)return 0;
    if(fscanf(f,"%2s\n%d %d\n%d\n",magic,&width,&height,&max)!=4||strcmp(magic,"P6")||max!=255||width!=640||height!=400){fclose(f);return 0;}
    size_t bytes=(size_t)width*height*3;unsigned char *rgb=malloc(bytes);if(!rgb){fclose(f);return 0;}
    if(fread(rgb,1,bytes,f)!=bytes){fclose(f);free(rgb);return 0;}fclose(f);
    for(int trial=0;trial<150;trial++){
        XWindowAttributes a;if(!XGetWindowAttributes(d,w,&a))break;
        if(a.width==width&&a.height==height){
            XImage *im=XGetImage(d,w,0,0,width,height,AllPlanes,ZPixmap);if(!im)break;
            int equal=1;
            for(int y=0;y<height&&equal;y++)for(int x=0;x<width&&equal;x++){
                if(x<32&&y<32)continue;
                unsigned long p=XGetPixel(im,x,y);size_t at=((size_t)y*width+x)*3;
                equal=component(p,im->red_mask)==rgb[at]&&component(p,im->green_mask)==rgb[at+1]&&component(p,im->blue_mask)==rgb[at+2];
            }
            XDestroyImage(im);if(equal){free(rgb);return 1;}
        }
        usleep(100000);
    }
    free(rgb);return 0;
}
static void close_window(Display *d,Window w) {
    XEvent close;memset(&close,0,sizeof(close));close.xclient.type=ClientMessage;close.xclient.window=w;
    close.xclient.message_type=XInternAtom(d,"WM_PROTOCOLS",False);close.xclient.format=32;
    close.xclient.data.l[0]=XInternAtom(d,"WM_DELETE_WINDOW",False);close.xclient.data.l[1]=CurrentTime;
    XSendEvent(d,w,False,NoEventMask,&close);XFlush(d);
}
int main(int argc,char **argv) {
    if(argc!=3)return 2;
    snprintf(key_helper,sizeof(key_helper),"%s/xtest-key",argv[1]);
    Display *d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<200&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(3);capture(d,w,argv[1],"01-start");key(d,w,XK_Return);
    if(!wait_reference(d,w,argv[2],"02-return"))return 10;
    capture(d,w,argv[1],"02-return");key(d,w,XK_p);
    if(!wait_reference(d,w,argv[2],"02a-player")){capture(d,w,argv[1],"failure-role");close_window(d,w);sleep(2);XCloseDisplay(d);return 11;}
    capture(d,w,argv[1],"02a-player");
    key(d,w,XK_F2);sleep(1);capture(d,w,argv[1],"03-scale");
    key(d,w,XK_F12);sleep(1);capture(d,w,argv[1],"04-original");
    key(d,w,XK_F12);sleep(1);capture(d,w,argv[1],"05-chinese");
    key(d,w,XK_F6);sleep(1);capture(d,w,argv[1],"06-manual");
    key(d,w,XK_Escape);sleep(1);capture(d,w,argv[1],"07-return");
    key(d,w,XK_F10);sleep(1);
    close_window(d,w);XCloseDisplay(d);return 0;
}
