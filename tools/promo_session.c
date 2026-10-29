/* 錄製實際玩家畫面；輸入仍沿已驗證XTEST。 */
#define main prior_probe_main
#include "player_gui_probe.c"
#undef main

static struct timespec started;
static void story_hd(Display*d,Window w){
    XWarpPointer(d,None,w,0,0,0,0,270,2);XSync(d,False);sleep(1);
    fake_key(1,"mouse-down");sleep(1);fake_key(1,"mouse-up");sleep(1);
    XWarpPointer(d,None,w,0,0,0,0,950,590);XSync(d,False);sleep(1);
}
static void mark(Display*d,Window w,const char*out,const char*name){
    struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);
    double at=now.tv_sec-started.tv_sec+(now.tv_nsec-started.tv_nsec)/1e9;
    printf("%s\t%.6f\n",name,at);fflush(stdout);capture(d,w,out,name);
}
int main(int argc,char**argv){
    if(argc!=3)return 2;
    const char*out=argv[1],*mode=argv[2];
    int story=getenv("DQK_PROMO_EDITION")&&!strcmp(getenv("DQK_PROMO_EDITION"),"story");
    snprintf(key_helper,sizeof(key_helper),"%s/xtest-key",out);
    Display*d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<200&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(2);char path[4096];snprintf(path,sizeof(path),"%s/window-id",out);FILE*f=fopen(path,"w");if(!f)return 5;fprintf(f,"%lu\n",w);fclose(f);
    XWindowAttributes geometry;Window child;int gx,gy;
    if(!XGetWindowAttributes(d,w,&geometry)||!XTranslateCoordinates(d,w,DefaultRootWindow(d),0,0,&gx,&gy,&child))return 21;
    snprintf(path,sizeof(path),"%s/window-rect.json",out);f=fopen(path,"w");if(!f)return 5;
    fprintf(f,"{\"rect\":[%d,%d,%d,%d],\"method\":\"X11 client coordinates before capture\"}\n",gx,gy,geometry.width,geometry.height);fclose(f);
    snprintf(path,sizeof(path),"%s/recording",out);
    for(int i=0;i<600&&access(path,F_OK);i++)usleep(100000);
    if(access(path,F_OK))return 18;
    clock_gettime(CLOCK_MONOTONIC,&started);
    mark(d,w,out,"title");sleep(3);
    if(!strcmp(mode,"normal")){
        key(d,w,XK_Return);key(d,w,XK_p);mark(d,w,out,"role");sleep(story?8:4);
        XWarpPointer(d,None,w,0,0,0,0,774,2);XSync(d,False);sleep(1);mark(d,w,out,"toolbar");sleep(story?8:3);
        XWarpPointer(d,None,w,0,0,0,0,950,590);XSync(d,False);
        key(d,w,XK_F6);mark(d,w,out,"manual");sleep(story?8:4);
        key(d,w,XK_Right);key(d,w,XK_Down);key(d,w,XK_Return);Window mw=wait_map_window(d,w);mark(d,mw,out,"map");sleep(story?10:4);
        close_map_key(d,mw,w);key(d,w,XK_Escape);key(d,w,XK_F7);mark(d,w,out,"guide");sleep(4);
        key(d,w,XK_Return);mark(d,w,out,"guide-body");sleep(story?6:4);
        if(story){
            key(d,w,XK_Escape);key(d,w,XK_Left);key(d,w,XK_Left);key(d,w,XK_Left);
            key(d,w,XK_Return);mark(d,w,out,"guide-chapter");sleep(4);
            key(d,w,XK_Escape);key(d,w,XK_Down);key(d,w,XK_Return);
            mw=wait_map_window(d,w);mark(d,mw,out,"guide-map");sleep(10);close_map_key(d,mw,w);
        }
    }else if(!strcmp(mode,"exploration")){
        key(d,w,XK_Right);key(d,w,XK_Up);key(d,w,XK_Left);
        key(d,w,XK_e);if(story){mark(d,w,out,"camp");sleep(8);}key(d,w,XK_Escape);sleep(3);mark(d,w,out,"cave");
        if(story){
            sleep(8);mark(d,w,out,"cave-motion");
            key(d,w,XK_Right);key(d,w,XK_Up);key(d,w,XK_Left);sleep(2);
            story_hd(d,w);mark(d,w,out,"cave-native");sleep(4);
            story_hd(d,w);mark(d,w,out,"cave-hd");sleep(5);
        }
    }else if(!strcmp(mode,"combat")){
        /* 先保留隊形與怪物的可讀鏡頭，再讓原版快速戰鬥自然推進。 */
        key(d,w,XK_v);key(d,w,XK_Escape);sleep(1);mark(d,w,out,"battle");sleep(4);
        key(d,w,XK_q);sleep(20);mark(d,w,out,"battle-after");
    }else return 2;
    snprintf(path,sizeof(path),"%s/stop",out);
    for(int i=0;i<600&&access(path,F_OK);i++)usleep(100000);
    close_window(d,w);XCloseDisplay(d);return 0;
}
