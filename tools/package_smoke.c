/* 只用正常視窗輸入驗證封包，沒有注入遊戲狀態。 */
#define main prior_probe_main
#include "player_gui_probe.c"
#undef main
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
        Window mw=wait_map_window(d,w);capture(d,mw,argv[1],"04-map-fullscreen");
        key(d,mw,XK_equal);capture(d,mw,argv[1],"05-map-zoom");
        close_map_key(d,mw,w);
        capture(d,w,argv[1],"06-map-index");
    }
    key(d,w,XK_Escape);close_window(d,w);XCloseDisplay(d);return 0;
}
