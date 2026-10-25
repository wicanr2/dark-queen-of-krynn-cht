/* DRAFT：重用既有 X11 擷取及按鍵傳送，只操作說明面板視窗。 */
#define main journal_driver_main
#include "x11_menu_driver.c"
#undef main

int main(int argc,char **argv) {
    if(argc!=3)return 2;
    Display *d=XOpenDisplay(NULL);if(!d)return 2;
    unsigned long pid=strtoul(argv[1],NULL,10);
    snprintf(status_path,sizeof status_path,"%s/latest.json",argv[2]);
    Window w=0;char json[8192],directory[4096],path[4096];
    struct timespec start,now,pause={0,10000000},present={0,80000000};
    clock_gettime(CLOCK_MONOTONIC,&start);
    for(;;) {
        clock_gettime(CLOCK_MONOTONIC,&now);
        if(now.tv_sec-start.tv_sec>60)return 4;
        if(!w)w=find_window(d,DefaultRootWindow(d),pid);
        reader_status(json,sizeof json);
        if(w && number(json,"step")==905000000ULL && number(json,"manual_inputs")==1 &&
           strstr(json,"\"reader_mode\":\"manual\""))break;
        nanosleep(&pause,NULL);
    }
    count_field="manual_inputs";
    KeySym keys[]={XK_Return,XK_Escape,XK_Right,XK_Return,XK_Escape,XK_Right,
                   XK_Return,XK_Page_Down,XK_Page_Up,XK_Escape,XK_F6};
    for(size_t phase=0;phase<sizeof keys/sizeof keys[0];phase++) {
        nanosleep(&present,NULL);XSync(d,False);
        reader_status(json,sizeof json);
        if(number(json,"step")!=905000000ULL || number(json,"manual_inputs")!=phase+1 ||
           !strstr(json,"\"reader_mode\":\"manual\""))return 7;
        snprintf(directory,sizeof directory,"%s/manual-%zu",argv[2],phase);
        if(mkdir(directory,0755))return 6;
        capture(d,w,directory,json);
        snprintf(path,sizeof path,"%s/latest.json",directory);
        FILE *f=fopen(path,"w");if(!f)return 6;fputs(json,f);fclose(f);
        send_key(d,w,keys[phase]);
    }
    XCloseDisplay(d);return 0;
}
