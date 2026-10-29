/* 共用已驗證XTEST與擷取；只改代表操作順序。 */
#define main prior_probe_main
#include "player_gui_probe.c"
#undef main

static void hd_click(Display *d,Window w){
    XWarpPointer(d,None,w,0,0,0,0,180,2);XSync(d,False);usleep(500000);
    fake_key(1,"mouse-down");usleep(200000);fake_key(1,"mouse-up");usleep(500000);
    XWarpPointer(d,None,w,0,0,0,0,620,370);XSync(d,False);usleep(500000);
}
int main(int argc,char **argv){
    if(argc!=3)return 2;
    snprintf(key_helper,sizeof(key_helper),"%s/xtest-key",argv[1]);
    Display *d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<900&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(2);capture(d,w,argv[1],"01-initial");
    if(!strcmp(argv[2],"exploration")){
        key(d,w,XK_Right);capture(d,w,argv[1],"02-turn");
        key(d,w,XK_Up);capture(d,w,argv[1],"03-move");
        key(d,w,XK_Left);capture(d,w,argv[1],"04-ready");
    }else if(!strcmp(argv[2],"combat")){
        key(d,w,XK_q);sleep(2);capture(d,w,argv[1],"04-ready");
    }else return 2;
    hd_click(d,w);capture(d,w,argv[1],"05-hd-off");
    hd_click(d,w);capture(d,w,argv[1],"06-hd-on");
    key(d,w,XK_F2);capture(d,w,argv[1],"07-scale3");
    key(d,w,XK_F10);close_window(d,w);XCloseDisplay(d);return 0;
}
