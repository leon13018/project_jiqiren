#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""機器人組合動作（中斷式）。

所有函數接受 cancel: threading.Event = None 參數。
ActionWorker 透過設 cancel + 呼叫 Act.stopAction() 中斷動作。
"""

import threading
import time
import ActionGroupControl as Act
import Board


class _Cancelled(Exception):
    """動作被取消（由 ActionWorker 內部捕捉，不對外）。"""
    pass


def _ck(cancel):
    """檢查 cancel 旗號，若已設則中斷。"""
    if cancel is not None and cancel.is_set():
        raise _Cancelled()


def _csleep(secs, cancel, step=0.05):
    """可中斷的 sleep（每 step 秒檢查一次 cancel）。"""
    end = time.time() + secs
    while time.time() < end:
        _ck(cancel)
        time.sleep(step)


# -------------------- 四肢動作 --------------------
def play_action(name, cancel=None):
    """播放 .d6a 四肢動作檔（廠商 vendor 動作組）。"""
    _ck(cancel)
    Act.runAction(name)   # 被 Act.stopAction() 打斷後會 return
    _ck(cancel)


# -------------------- 頭部動作 --------------------
def nod_head(times=1, cancel=None):
    """點頭（舵機 1）。"""
    for _ in range(times):
        _ck(cancel)
        Board.setPWMServoPulse(1, 1700, 300)
        _csleep(0.3, cancel)
        _ck(cancel)
        Board.setPWMServoPulse(1, 1500, 300)
        _csleep(0.3, cancel)


def shake_head(times=1, cancel=None):
    """搖頭（舵機 2）。"""
    for _ in range(times):
        _ck(cancel)
        Board.setPWMServoPulse(2, 1800, 300)
        _csleep(0.3, cancel)
        _ck(cancel)
        Board.setPWMServoPulse(2, 1500, 300)
        _csleep(0.3, cancel)
        _ck(cancel)
        Board.setPWMServoPulse(2, 1300, 300)
        _csleep(0.3, cancel)
        _ck(cancel)
        Board.setPWMServoPulse(2, 1500, 300)
        _csleep(0.3, cancel)


def look_at_screen(cancel=None):
    """頭部轉向右側螢幕。"""
    _ck(cancel)
    Board.setPWMServoPulse(2, 1200, 500)
    _csleep(0.6, cancel)


def look_forward(cancel=None):
    """頭部回正。"""
    _ck(cancel)
    Board.setPWMServoPulse(1, 1500, 300)
    Board.setPWMServoPulse(2, 1500, 300)
    _csleep(0.3, cancel)


# -------------------- 場景組合動作 --------------------
def action_idle(cancel=None):
    """叫賣模式：揮手 + 搖頭 + 回正。"""
    play_action('wave_hand', cancel=cancel)
    shake_head(2, cancel=cancel)
    look_forward(cancel=cancel)


def action_greet(cancel=None):
    """歡迎模式：鞠躬 + 點頭 + 回正。"""
    play_action('bow', cancel=cancel)
    nod_head(2, cancel=cancel)
    look_forward(cancel=cancel)


def action_pay(cancel=None):
    """結帳模式：指向螢幕 + 轉頭 + 鞠躬 + 回正。"""
    play_action('point_screen', cancel=cancel)
    look_at_screen(cancel=cancel)
    _csleep(2, cancel)
    look_forward(cancel=cancel)
    play_action('bow', cancel=cancel)
    look_forward(cancel=cancel)
