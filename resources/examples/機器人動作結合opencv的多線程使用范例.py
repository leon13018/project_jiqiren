import cv2
import time
import threading
import ActionGroupControl as Act

def forward():
    Act.runAction('go_forward')

def stop():
    Act.runAction('stand')

def backward():
    Act.runAction('back')

def right():
    Act.runAction('turn_right')

def left():
    Act.runAction('turn_left')

cap = cv2.VideoCapture(0)

lastCmd = ''

def runBot():
    global lastCmd
    commandList= {ord('w'):forward,
                  ord('s'):stop,
                  ord('a'):left,
                  ord('x'):backward,
                  ord('d'):right}
    while 1:
        if lastCmd in commandList:
            commandList[lastCmd]()
            lastCmd = ''
        
def imgRun():
    global lastCmd
    key = ''
    while 1:
        ret,frame = cap.read()
        
        key = cv2.waitKey(1) & 0xff
        
        if key == ord('q'):
            cv2.destroyAllWindows()
            cap.release()
            break
        elif key in [ord('w'),ord('s'),ord('a'),ord('x'),ord('d')]:
            lastCmd = key
        else:
            pass

        if lastCmd == ord('w'):
            cv2.putText(frame,'W',(50,50),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,255),3,cv2.LINE_AA)
        else:
            cv2.putText(frame,'W',(50,50),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),3,cv2.LINE_AA)

        if lastCmd == ord('s'):
            cv2.putText(frame,'S',(50,80),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,255),3,cv2.LINE_AA)
        else:
            cv2.putText(frame,'S',(50,80),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),3,cv2.LINE_AA)

        if lastCmd == ord('a'):
            cv2.putText(frame,'A',(30,80),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,255),3,cv2.LINE_AA)
        else:
            cv2.putText(frame,'A',(30,80),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),3,cv2.LINE_AA)

        if lastCmd == ord('d'):
            cv2.putText(frame,'D',(70,80),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,255),3,cv2.LINE_AA)
        else:
            cv2.putText(frame,'D',(70,80),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),3,cv2.LINE_AA)
            
        if lastCmd == ord('x'):
            cv2.putText(frame,'X',(50,110),cv2.FONT_HERSHEY_COMPLEX,1,(0,255,255),3,cv2.LINE_AA)
        else:
            cv2.putText(frame,'X',(50,110),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),3,cv2.LINE_AA)
        cv2.imshow('frame',frame)
thread = threading.Thread(target=runBot,)
thread.start()
imgRun()