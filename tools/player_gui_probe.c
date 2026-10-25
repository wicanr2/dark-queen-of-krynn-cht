/* 正常玩家視窗的有界抽樣。只送 X11 鍵盤與正常關窗訊息，不修改遊戲狀態。 */
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <time.h>

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
    XKeyEvent e;memset(&e,0,sizeof(e));e.display=d;e.window=w;e.root=DefaultRootWindow(d);
    struct timespec stamp;clock_gettime(CLOCK_MONOTONIC,&stamp);
    e.time=(Time)(stamp.tv_sec*1000+stamp.tv_nsec/1000000);e.same_screen=True;e.keycode=XKeysymToKeycode(d,sym);e.x=e.y=20;
    XSetInputFocus(d,w,RevertToParent,CurrentTime);
    e.type=KeyPress;XSendEvent(d,w,True,KeyPressMask,(XEvent*)&e);XFlush(d);usleep(1000000);
    clock_gettime(CLOCK_MONOTONIC,&stamp);e.time=(Time)(stamp.tv_sec*1000+stamp.tv_nsec/1000000);
    e.type=KeyRelease;XSendEvent(d,w,True,KeyReleaseMask,(XEvent*)&e);XFlush(d);
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
int main(int argc,char **argv) {
    if(argc!=2)return 2;
    Display *d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<200&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(3);capture(d,w,argv[1],"01-start");key(d,w,XK_Return);sleep(3);
    capture(d,w,argv[1],"02-return");key(d,w,XK_p);sleep(2);capture(d,w,argv[1],"02a-player");
    key(d,w,XK_F2);sleep(1);capture(d,w,argv[1],"03-scale");
    key(d,w,XK_F12);sleep(1);capture(d,w,argv[1],"04-original");
    key(d,w,XK_F12);sleep(1);capture(d,w,argv[1],"05-chinese");
    key(d,w,XK_F6);sleep(1);capture(d,w,argv[1],"06-manual");
    key(d,w,XK_Escape);sleep(1);capture(d,w,argv[1],"07-return");
    key(d,w,XK_F10);sleep(1);
    XEvent close;memset(&close,0,sizeof(close));close.xclient.type=ClientMessage;close.xclient.window=w;
    close.xclient.message_type=XInternAtom(d,"WM_PROTOCOLS",False);close.xclient.format=32;
    close.xclient.data.l[0]=XInternAtom(d,"WM_DELETE_WINDOW",False);close.xclient.data.l[1]=CurrentTime;
    XSendEvent(d,w,False,NoEventMask,&close);XFlush(d);XCloseDisplay(d);return 0;
}
