/* 只用正常視窗輸入驗證封包，沒有注入遊戲狀態。 */
#define main prior_probe_main
#include "player_gui_probe.c"
#undef main
static int wait_map_content(Display*d,Window w,const char*out){
    for(int attempt=0;attempt<150;attempt++){
        XWindowAttributes a;if(!XGetWindowAttributes(d,w,&a))return 0;
        XImage*im=XGetImage(d,w,0,0,a.width,a.height,AllPlanes,ZPixmap);int paper=0,ink=0;
        if(im){for(int y=0;y<a.height;y+=2)for(int x=0;x<a.width;x+=2){unsigned long p=XGetPixel(im,x,y);unsigned r=component(p,im->red_mask),g=component(p,im->green_mask),b=component(p,im->blue_mask);if(y>=48&&y<a.height-56&&r>100&&g>100&&b>50)paper++;if(y>=10&&y<48&&r>180&&g>160&&b<190)ink++;}XDestroyImage(im);}
        if(paper>a.width*a.height/40&&ink>10){char path[4096];snprintf(path,sizeof(path),"%s/map-content-ready-ms.txt",out);FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%d\n",attempt*100);fclose(f);return 1;}usleep(100000);
    }
    return 0;
}
static int wait_index_header(Display*d,Window w,const char*out){
    for(int attempt=0;attempt<120;attempt++){
        XWindowAttributes a;
        if(!XGetWindowAttributes(d,w,&a))return 0;
        int x=32*a.width/640,y=16*a.height/400,ww=592*a.width/640,hh=16*a.height/400;
        XImage*im=XGetImage(d,w,x,y,ww,hh,AllPlanes,ZPixmap);int ink=0;
        if(im){for(int yy=0;yy<hh;yy++)for(int xx=0;xx<ww;xx++){unsigned long p=XGetPixel(im,xx,yy);if(component(p,im->red_mask)>180&&component(p,im->green_mask)>160&&component(p,im->blue_mask)<140)ink++;}XDestroyImage(im);}
        if(ink>30){char path[4096];snprintf(path,sizeof(path),"%s/map-ready-ms.txt",out);FILE*f=fopen(path,"w");if(!f)return 0;fprintf(f,"%d\n",attempt*100);fclose(f);return 1;}
        usleep(100000);
    }
    return 0;
}
int main(int argc,char**argv){
    if(argc!=2)return 2;
    snprintf(key_helper,sizeof(key_helper),"%s/xtest-key",argv[1]);
    Display*d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<600&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(3);capture(d,w,argv[1],"01-title");
    key(d,w,XK_Return);sleep(3);key(d,w,XK_p);sleep(3);capture(d,w,argv[1],"02-role");
    key(d,w,XK_F6);sleep(2);capture(d,w,argv[1],"03-manual");
    if(getenv("DQK_VERIFY_MAP_WINDOW")&&!strcmp(getenv("DQK_VERIFY_MAP_WINDOW"),"1")){
        reader_input=1;
        key(d,w,XK_Right);key(d,w,XK_Down);key(d,w,XK_Return);
        Window mw=wait_map_window(d,w);if(!wait_map_content(d,mw,argv[1]))return 25;capture(d,mw,argv[1],"04-map-fullscreen");
        key(d,mw,XK_equal);capture(d,mw,argv[1],"05-map-zoom");
        int wm=getenv("DQK_MAP_CLOSE_WM")&&!strcmp(getenv("DQK_MAP_CLOSE_WM"),"1");
        char helper[4096];snprintf(helper,sizeof(helper),"%s/native-close.exe",argv[1]);int native=wm&&access(helper,F_OK)==0;
        char method[4096];snprintf(method,sizeof(method),"%s/map-close-method.txt",argv[1]);FILE*mf=fopen(method,"w");if(!mf)return 5;fprintf(mf,"%s\n",native?"win32-close":wm?"window-close":"escape");fclose(mf);
        if(native){pid_t p=fork();if(p<0)return 23;if(!p){execlp("wine","wine","Z:/out/native-close.exe",(char*)NULL);_exit(23);}int status;if(waitpid(p,&status,0)<0||!WIFEXITED(status)||WEXITSTATUS(status))return 23;}
        if(wm){if(!native)close_window(d,mw);XSetInputFocus(d,w,RevertToParent,CurrentTime);XSync(d,False);sleep(3);}else close_map_key(d,mw,w);
        if(!wait_index_header(d,w,argv[1]))return 24;
        capture(d,w,argv[1],"06-map-index");
        close_window(d,w);XCloseDisplay(d);return 0; /* 在前端目錄暫停時關窗，避免任意截斷DOS繪圖交易。 */
    }
    key(d,w,XK_Escape);close_window(d,w);XCloseDisplay(d);return 0;
}
