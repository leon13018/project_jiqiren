#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import ActionGroupControl as Act
import Board


# -------------------- 四肢动作 --------------------
def play_action(name):
    """播放 .d6a 四肢动作文件"""
    Act.runAction(name)


# -------------------- 头部动作 --------------------
def nod_head(times=1):
    """点头（舵机1）"""
    for _ in range(times):
        Board.setPWMServoPulse(1, 1700, 300)
        time.sleep(0.3)
        Board.setPWMServoPulse(1, 1500, 300)
        time.sleep(0.3)


def shake_head(times=1):
    """摇头（舵机2）"""
    for _ in range(times):
        Board.setPWMServoPulse(2, 1800, 300)
        time.sleep(0.3)
        Board.setPWMServoPulse(2, 1500, 300)
        time.sleep(0.3)
        Board.setPWMServoPulse(2, 1300, 300)
        time.sleep(0.3)
        Board.setPWMServoPulse(2, 1500, 300)
        time.sleep(0.3)


def look_at_screen():
    """头部转向右侧屏幕"""
    Board.setPWMServoPulse(2, 1200, 500)
    time.sleep(0.6)


def look_forward():
    """头部回正"""
    Board.setPWMServoPulse(1, 1500, 300)
    Board.setPWMServoPulse(2, 1500, 300)
    time.sleep(0.3)


# -------------------- 场景组合动作 --------------------
def action_idle():
    """叫卖模式：挥手 + 摇头 + 回正"""
    play_action('wave_hand')
    shake_head(2)
    look_forward()


def action_greet():
    """欢迎模式：鞠躬 + 点头 + 回正"""
    play_action('bow')
    nod_head(2)
    look_forward()


def action_pay():
    """结账模式：指向屏幕 + 转头 + 鞠躬 + 回正"""
    play_action('point_screen')
    look_at_screen()
    time.sleep(2)
    look_forward()
    play_action('bow')
    look_forward()