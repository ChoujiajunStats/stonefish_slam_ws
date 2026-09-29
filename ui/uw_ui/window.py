"""Request Qt's normal window close before ROS launch tears down the context."""
import ctypes as C
from ctypes.util import find_library
import json,time,shutil


class ClientData(C.Union):
    _fields_=[('b',C.c_char*20),('s',C.c_short*10),('l',C.c_long*5)]


class ClientMessage(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),
        ('display',C.c_void_p),('window',C.c_ulong),('message_type',C.c_ulong),
        ('format',C.c_int),('data',ClientData)]


class KeyEvent(C.Structure):
    _fields_=[('type',C.c_int),('serial',C.c_ulong),('send_event',C.c_int),
        ('display',C.c_void_p),('window',C.c_ulong),('root',C.c_ulong),('subwindow',C.c_ulong),
        ('time',C.c_ulong),('x',C.c_int),('y',C.c_int),('x_root',C.c_int),('y_root',C.c_int),
        ('state',C.c_uint),('keycode',C.c_uint),('same_screen',C.c_int)]


class XEvent(C.Union):
    _fields_=[('client',ClientMessage),('key',KeyEvent),('pad',C.c_long*24)]


class RunWindows:
    """Arrange only new X11 clients whose PIDs belong to this launch.

    Existing clients are excluded even when another container uses the same PID.
    No dependency on a desktop automation utility and no persistent focus grab.
    """
    def __init__(self, output):
        self.output=output;self.pids={};self.baseline=set();self.error=None
        try:
            self.x=C.CDLL(find_library('X11'))
            for name,args,result in [
                ('XOpenDisplay',[C.c_char_p],C.c_void_p),
                ('XDefaultRootWindow',[C.c_void_p],C.c_ulong),
                ('XInternAtom',[C.c_void_p,C.c_char_p,C.c_int],C.c_ulong),
                ('XGetWindowProperty',[C.c_void_p,C.c_ulong,C.c_ulong,C.c_long,C.c_long,C.c_int,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_int),C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_void_p)],C.c_int),
                ('XSendEvent',[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(XEvent)],C.c_int),
                ('XDefaultScreen',[C.c_void_p],C.c_int),
                ('XDisplayWidth',[C.c_void_p,C.c_int],C.c_int),
                ('XDisplayHeight',[C.c_void_p,C.c_int],C.c_int),
                ('XRaiseWindow',[C.c_void_p,C.c_ulong],C.c_int),
                ('XFree',[C.c_void_p],C.c_int),('XFlush',[C.c_void_p],C.c_int),
                ('XCloseDisplay',[C.c_void_p],C.c_int)]:
                fn=getattr(self.x,name);fn.argtypes=args;fn.restype=result
            d=self.open()
            try:self.baseline=set(self.property(d,self.x.XDefaultRootWindow(d),'_NET_CLIENT_LIST'))
            finally:self.x.XCloseDisplay(d)
        except Exception as error:self.error=str(error)

    def open(self):
        d=self.x.XOpenDisplay(None)
        if not d:raise RuntimeError('No authorized X display')
        return d

    def atom(self,d,name):return self.x.XInternAtom(d,name.encode(),False)

    def property(self,d,window,name):
        actual=C.c_ulong();fmt=C.c_int();n=C.c_ulong();remaining=C.c_ulong();data=C.c_void_p()
        code=self.x.XGetWindowProperty(d,window,self.atom(d,name),0,4096,False,0,C.byref(actual),C.byref(fmt),C.byref(n),C.byref(remaining),C.byref(data))
        try:
            if code or not data:return []
            if fmt.value==32:return list(C.cast(data,C.POINTER(C.c_ulong))[:n.value])
            if fmt.value==8:return C.string_at(data,n.value).decode(errors='replace')
            return []
        finally:
            if data:self.x.XFree(data)

    def show(self):
        record=dict(run_id=self.output.name,wall_ns=time.monotonic_ns(),shown=False)
        d=None
        try:
            if self.error:raise RuntimeError(self.error)
            d=self.open();root=self.x.XDefaultRootWindow(d);matches={}
            for window in self.property(d,root,'_NET_CLIENT_LIST'):
                if window in self.baseline:continue
                pid=self.property(d,window,'_NET_WM_PID');title=self.property(d,window,'_NET_WM_NAME') or self.property(d,window,'WM_NAME')
                cls=self.property(d,window,'WM_CLASS')
                for label,expected in self.pids.items():
                    if pid!=[expected]:continue
                    if label=='rviz' and self.output.name in str(title) and 'rviz' in str(cls).lower():matches.setdefault(label,[]).append(window)
                    if label=='stonefish_simulator' and 'stonefish_simulator' in str(cls):matches.setdefault(label,[]).append(window)
            if any(len(matches.get(k,[]))!=1 for k in ('rviz','stonefish_simulator')):
                raise RuntimeError('Waiting for both unique run clients')
            screen=self.x.XDefaultScreen(d);width=self.x.XDisplayWidth(d,screen);height=self.x.XDisplayHeight(d,screen)
            # Keep the simulator at its original 960x720 render size. Its GUI
            # resolution must not unexpectedly multiply the rendering load.
            sw,sh=960,720;rw=min(2100,max(800,width-sw-100));rh=min(1200,max(600,height-160))
            positions={'rviz':(30,80,rw,rh),'stonefish_simulator':(rw+65,80,sw,sh)}
            if width<1900:positions['stonefish_simulator']=(max(0,width-sw-20),max(80,height-sh-60),sw,sh)
            def send(window,kind,values):
                event=XEvent();event.client.type=33;event.client.display=d;event.client.window=window
                event.client.message_type=self.atom(d,kind);event.client.format=32
                for i,value in enumerate(values):event.client.data.l[i]=value
                self.x.XSendEvent(d,root,False,(1<<19)|(1<<20),C.byref(event))
            for label in ('rviz','stonefish_simulator'):
                window=matches[label][0]
                send(window,'_NET_WM_STATE',[0,self.atom(d,'_NET_WM_STATE_MAXIMIZED_HORZ'),self.atom(d,'_NET_WM_STATE_MAXIMIZED_VERT'),2])
                send(window,'_NET_MOVERESIZE_WINDOW',[(2<<12)|(15<<8),*positions[label]])
                self.x.XRaiseWindow(d,window)
                send(window,'_NET_ACTIVE_WINDOW',[2,0,0])
            self.x.XFlush(d)
            record.update(shown=True,clients={k:hex(v[0]) for k,v in matches.items()},requested_geometry=positions,display_pixels=[width,height])
        except Exception as error:record['error']=str(error)
        finally:
            if d:self.x.XCloseDisplay(d)
            (self.output/'gui-show.json').write_text(json.dumps(record,indent=2)+'\n')
        return record['shown']


def show_window_actions(output,simulator,rviz):
    """Launch-local, bounded retries; GUI failure never grants control authority."""
    from launch.actions import RegisterEventHandler,TimerAction,OpaqueFunction
    from launch.event_handlers import OnProcessStart
    windows=RunWindows(output);attempts=[0]
    def started(label):
        def callback(event,context):windows.pids[label]=event.pid
        return callback
    def attempt(context):
        attempts[0]+=1
        if context.is_shutdown or windows.show() or attempts[0]>=30:return []
        return [TimerAction(period=2.,actions=[OpaqueFunction(function=attempt)])]
    return [RegisterEventHandler(OnProcessStart(target_action=simulator,on_start=started('stonefish_simulator'))),
        RegisterEventHandler(OnProcessStart(target_action=rviz,on_start=started('rviz'))),
        TimerAction(period=3.,actions=[OpaqueFunction(function=attempt)])]


def close_rviz(output):
    """Match the unique run path in the client title; never close other project windows."""
    record={'wall_ns':time.monotonic_ns(),'operation':'WM_DELETE_WINDOW','run_id':output.name,'requested':False}
    display=None
    try:
        x=C.CDLL(find_library('X11'))
        x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
        x.XDefaultRootWindow.argtypes=[C.c_void_p];x.XDefaultRootWindow.restype=C.c_ulong
        x.XQueryTree.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.POINTER(C.c_ulong)),C.POINTER(C.c_uint)]
        x.XFetchName.argtypes=[C.c_void_p,C.c_ulong,C.POINTER(C.c_void_p)]
        x.XFree.argtypes=[C.c_void_p]
        x.XInternAtom.argtypes=[C.c_void_p,C.c_char_p,C.c_int];x.XInternAtom.restype=C.c_ulong
        x.XSendEvent.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_long,C.POINTER(XEvent)]
        x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
        display=x.XOpenDisplay(None)
        if not display:raise RuntimeError('No authorized X display')
        pending=[(x.XDefaultRootWindow(display),0)];matches=[]
        while pending:
            window,depth=pending.pop();name=C.c_void_p()
            if x.XFetchName(display,window,C.byref(name)) and name.value:
                title=C.string_at(name).decode(errors='replace');x.XFree(name)
                if str(output) in title and title.endswith(' - RViz'):matches.append(window)
            if depth<4:
                root=C.c_ulong();parent=C.c_ulong();children=C.POINTER(C.c_ulong)();count=C.c_uint()
                if x.XQueryTree(display,window,C.byref(root),C.byref(parent),C.byref(children),C.byref(count)):
                    pending.extend((children[i],depth+1) for i in range(count.value))
                    if children:x.XFree(children)
        if len(matches)!=1:raise RuntimeError('Expected one RViz client for this run, found '+str(len(matches)))
        # Save only this run's generated layout so Qt has no modal save prompt.
        # Preserve the pre-save layout as a separate artifact.
        shutil.copy2(output/'inspect.rviz',output/'inspect.before-close.rviz')
        x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=C.c_ulong
        x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_ubyte
        key=XEvent();key.key.display=display;key.key.window=matches[0];key.key.root=x.XDefaultRootWindow(display)
        key.key.state=4;key.key.keycode=x.XKeysymToKeycode(display,x.XStringToKeysym(b's'));key.key.same_screen=1
        key.key.type=2;x.XSendEvent(display,matches[0],1,1,C.byref(key))
        key.key.type=3;x.XSendEvent(display,matches[0],1,2,C.byref(key));x.XFlush(display);time.sleep(.3)
        current=C.c_void_p()
        if x.XFetchName(display,matches[0],C.byref(current)) and current.value:
            record['title_after_save']=C.string_at(current).decode(errors='replace');x.XFree(current)
        event=XEvent();event.client.type=33;event.client.display=display;event.client.window=matches[0]
        event.client.message_type=x.XInternAtom(display,b'WM_PROTOCOLS',0);event.client.format=32
        event.client.data.l[0]=x.XInternAtom(display,b'WM_DELETE_WINDOW',0);event.client.data.l[1]=0
        if not x.XSendEvent(display,matches[0],0,0,C.byref(event)):raise RuntimeError('XSendEvent failed')
        x.XFlush(display);record.update(requested=True,window_id=hex(matches[0]))
    except Exception as error:record['error']=str(error)
    finally:
        if display:x.XCloseDisplay(display)
        (output/'gui-close.json').write_text(json.dumps(record,indent=2)+'\n')
    return record['requested']
