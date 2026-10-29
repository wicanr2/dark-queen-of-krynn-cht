/* 錄製實際玩家畫面；輸入仍沿已驗證XTEST。 */
#define main prior_probe_main
#include "player_gui_probe.c"
#undef main

static struct timespec started;
static void mark(Display*d,Window w,const char*out,const char*name){
    struct timespec now;clock_gettime(CLOCK_MONOTONIC,&now);
    double at=now.tv_sec-started.tv_sec+(now.tv_nsec-started.tv_nsec)/1e9;
    printf("%s\t%.6f\n",name,at);fflush(stdout);capture(d,w,out,name);
}
int main(int argc,char**argv){
    if(argc!=3)return 2;
    const char*out=argv[1],*mode=argv[2];
    snprintf(key_helper,sizeof(key_helper),"%s/xtest-key",out);
    Display*d=XOpenDisplay(NULL);if(!d)return 6;Window w=0;
    for(int i=0;i<200&&!w;i++){w=find_window(d,DefaultRootWindow(d));usleep(100000);}if(!w)return 7;
    sleep(2);char path[4096];snprintf(path,sizeof(path),"%s/window-id",out);FILE*f=fopen(path,"w");if(!f)return 5;fprintf(f,"%lu\n",w);fclose(f);
    snprintf(path,sizeof(path),"%s/recording",out);
    for(int i=0;i<600&&access(path,F_OK);i++)usleep(100000);
    if(access(path,F_OK))return 18;
    clock_gettime(CLOCK_MONOTONIC,&started);
    mark(d,w,out,"title");sleep(3);
    if(!strcmp(mode,"normal")){
        key(d,w,XK_Return);key(d,w,XK_p);mark(d,w,out,"role");sleep(4);
        XWarpPointer(d,None,w,0,0,0,0,774,2);XSync(d,False);sleep(1);mark(d,w,out,"toolbar");sleep(3);
        XWarpPointer(d,None,w,0,0,0,0,950,590);XSync(d,False);
        key(d,w,XK_F6);mark(d,w,out,"manual");sleep(4);
        key(d,w,XK_Right);key(d,w,XK_Down);key(d,w,XK_Return);mark(d,w,out,"map");sleep(4);
        key(d,w,XK_Escape);key(d,w,XK_Escape);key(d,w,XK_F7);mark(d,w,out,"guide");sleep(4);
        key(d,w,XK_Return);mark(d,w,out,"guide-body");sleep(4);
    }else if(!strcmp(mode,"exploration")){
        key(d,w,XK_Right);key(d,w,XK_Up);key(d,w,XK_Left);
        key(d,w,XK_e);key(d,w,XK_Escape);sleep(3);mark(d,w,out,"cave");
    }else if(!strcmp(mode,"combat")){
        key(d,w,XK_q);sleep(20);key(d,w,XK_v);key(d,w,XK_Escape);sleep(3);mark(d,w,out,"battle");
    }else return 2;
    snprintf(path,sizeof(path),"%s/stop",out);
    for(int i=0;i<600&&access(path,F_OK);i++)usleep(100000);
    close_window(d,w);XCloseDisplay(d);return 0;
}
