#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
连点器 (Auto Clicker Pro) - 屏幕点击自动化工具

功能：
  1. 手动指定位置点击（坐标输入 / 屏幕取点）
  2. 设置间隔时间、点击次数、速度倍率
  3. 操作录制（记录点击位置与时间戳）
  4. 录制复现（支持速度调节 / 循环播放）
  5. 储存 / 重命名 / 删除录制文件

快捷键：F6 开始/停止 | Esc 取消取点
安全退出：将鼠标移至屏幕左上角
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  依赖自动安装
# ═══════════════════════════════════════════════════════════════
def _ensure_deps():
    """检查并自动安装依赖"""
    missing = []
    for mod, pkg in [('pyautogui', 'pyautogui'), ('pynput', 'pynput')]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"正在安装依赖: {', '.join(missing)} ...")
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install'] + missing + ['-q']
        )
        print("依赖安装完成！")

_ensure_deps()

import pyautogui
from pynput import mouse as pynput_mouse
from pynput import keyboard as pynput_keyboard

# pyautogui 安全设置
pyautogui.FAILSAFE = True    # 鼠标移至左上角 → 紧急停止
pyautogui.PAUSE  = 0.005


# ═══════════════════════════════════════════════════════════════
#  ClickEngine — 点击引擎
# ═══════════════════════════════════════════════════════════════
class ClickEngine:
    """管理自动点击的启动、停止与进度回调"""

    def __init__(self):
        self._running = False
        self._lock = threading.Lock()

    @property
    def running(self):
        with self._lock:
            return self._running

    def start(self, x, y, count, interval_ms,
              button='left', speed=1.0,
              on_progress=None, on_done=None):
        """
        启动自动点击
          count      — 点击次数 (0 = 无限)
          interval_ms— 基础间隔 (毫秒)
          speed      — 速度倍率
        """
        with self._lock:
            if self._running:
                return
            self._running = True

        threading.Thread(
            target=self._loop,
            args=(x, y, count, interval_ms, button, speed,
                  on_progress, on_done),
            daemon=True
        ).start()

    def stop(self):
        with self._lock:
            self._running = False

    # ---- 内部 ----
    def _loop(self, x, y, count, interval_ms, button, speed,
              on_progress, on_done):
        interval = max(interval_ms / 1000.0 / speed, 0.005)
        clicked = 0
        err = None
        try:
            while True:
                with self._lock:
                    if not self._running:
                        break
                if 0 < count <= clicked:
                    break
                pyautogui.click(x=int(x), y=int(y), button=button)
                clicked += 1
                if on_progress:
                    try:
                        on_progress(clicked, count)
                    except Exception:
                        pass
                if 0 < count <= clicked:
                    break
                time.sleep(interval)
        except pyautogui.FailSafeException:
            err = "安全退出：鼠标已移至屏幕左上角"
        except Exception as e:
            err = str(e)
        finally:
            with self._lock:
                self._running = False
            if on_done:
                try:
                    on_done(err)
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════
#  Recorder — 操作录制器
# ═══════════════════════════════════════════════════════════════
class Recorder:
    """录制点击操作、播放、保存、管理录制文件"""

    def __init__(self, rec_dir=None):
        self.rec_dir = Path(rec_dir) if rec_dir else Path(__file__).parent / "recordings"
        self.rec_dir.mkdir(parents=True, exist_ok=True)

        self._recording = False
        self._playing   = False
        self._events    = []
        self._t0        = None
        self._ml        = None      # pynput mouse listener
        self._on_event  = None      # 录制回调

    # ---- 属性 ----
    @property
    def recording(self):
        return self._recording

    @property
    def playing(self):
        return self._playing

    @property
    def events(self):
        return list(self._events)

    # ---- 录制 ----
    def start_recording(self, on_event=None):
        if self._recording:
            return
        self._recording = True
        self._events    = []
        self._t0        = time.time()
        self._on_event  = on_event

        def _on_click(x, y, button, pressed):
            if not self._recording:
                return False
            if not pressed:                 # 只记录按下事件
                return True
            btn = {
                pynput_mouse.Button.left:   'left',
                pynput_mouse.Button.right:  'right',
                pynput_mouse.Button.middle: 'middle',
            }.get(button, 'left')
            ev = {
                'type':   'click',
                'x':      int(x),
                'y':      int(y),
                'button': btn,
                'time':   round(time.time() - self._t0, 3),
            }
            self._events.append(ev)
            if self._on_event:
                try:
                    self._on_event('add', ev)
                except Exception:
                    pass
            return True

        self._ml = pynput_mouse.Listener(on_click=_on_click)
        self._ml.start()

    def stop_recording(self):
        self._recording = False
        if self._ml:
            self._ml.stop()
            self._ml = None

    # ---- 复现 ----
    def play(self, events=None, speed=1.0, loop=False,
             on_progress=None, on_done=None):
        if self._playing:
            return
        ev_list = events if events is not None else self._events
        if not ev_list:
            return
        self._playing = True

        def _run():
            err = None
            try:
                while self._playing:
                    prev = 0
                    for i, ev in enumerate(ev_list):
                        if not self._playing:
                            return
                        delay = (ev['time'] - prev) / speed
                        if delay > 0 and i > 0:
                            time.sleep(delay)
                        prev = ev['time']
                        if not self._playing:
                            return
                        if ev['type'] == 'click':
                            pyautogui.click(
                                x=ev['x'], y=ev['y'],
                                button=ev.get('button', 'left')
                            )
                        if on_progress:
                            try:
                                on_progress(i + 1, len(ev_list))
                            except Exception:
                                pass
                    if not loop:
                        break
            except pyautogui.FailSafeException:
                err = "安全退出：鼠标已移至屏幕左上角"
            except Exception as e:
                err = str(e)
            finally:
                self._playing = False
                if on_done:
                    try:
                        on_done(err)
                    except Exception:
                        pass

        threading.Thread(target=_run, daemon=True).start()

    def stop_playback(self):
        self._playing = False

    # ---- 存储 ----
    @staticmethod
    def _safe_name(name):
        safe = "".join(c for c in name if c.isalnum() or c in '_- .').strip()
        return safe or "unnamed"

    def save(self, name, events=None):
        ev_list = events if events is not None else self._events
        if not ev_list:
            return None
        name = self._safe_name(name)
        path = self.rec_dir / f"{name}.json"
        data = {
            'name':        name,
            'created':     datetime.now().isoformat(),
            'event_count': len(ev_list),
            'duration':    round(ev_list[-1]['time'], 3),
            'events':      ev_list,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)

    def load(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_all(self):
        result = []
        for p in sorted(self.rec_dir.glob('*.json'),
                        key=lambda f: f.stat().st_mtime, reverse=True):
            try:
                d = self.load(p)
                result.append({
                    'path':     str(p),
                    'name':     d.get('name', p.stem),
                    'created':  d.get('created', ''),
                    'count':    d.get('event_count', 0),
                    'duration': d.get('duration', 0),
                    'events':   d.get('events', []),
                })
            except Exception:
                pass
        return result

    def rename(self, old_path, new_name):
        old = Path(old_path)
        new_name = self._safe_name(new_name)
        new = old.parent / f"{new_name}.json"
        if new.exists() and new != old:
            return False
        old.rename(new)
        try:
            d = self.load(str(new))
            d['name'] = new_name
            with open(new, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return str(new)

    def delete(self, path):
        try:
            Path(path).unlink()
            return True
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
#  AutoClickerApp — 主界面
# ═══════════════════════════════════════════════════════════════
class AutoClickerApp:

    def __init__(self, root):
        self.root = root
        self.root.title("🖱️ 连点器 - Auto Clicker Pro")
        self.root.geometry("660x780")
        self.root.minsize(560, 660)

        self.engine   = ClickEngine()
        self.recorder = Recorder()

        self._picking  = False
        self._pick_ml  = None
        self._kb_l     = None

        self._build_ui()
        self._start_kb_listener()
        self._tick_pos()

        self.root.protocol("WM_DELETE_WINDOW", self._quit)

    # ════════════════ UI 构建 ════════════════

    def _build_ui(self):
        pad = dict(padx=10, pady=4)

        # ---- 顶部提示 ----
        top = ttk.Frame(self.root)
        top.pack(fill='x', **pad)
        ttk.Label(
            top,
            text="快捷键: F6 开始/停止 | Esc 取消取点 | 安全退出: 鼠标移至左上角",
            foreground='gray',
            font=('Microsoft YaHei UI', 8)
        ).pack(anchor='w')

        # ---- Notebook ----
        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, **pad)

        f1 = ttk.Frame(nb, padding=12)
        nb.add(f1, text='  🖱️ 手动点击  ')
        self._build_manual_tab(f1)

        f2 = ttk.Frame(nb, padding=12)
        nb.add(f2, text='  🎬 操作录制  ')
        self._build_record_tab(f2)

        f3 = ttk.Frame(nb, padding=12)
        nb.add(f3, text='  📁 录制管理  ')
        self._build_manage_tab(f3)

        # ---- 状态栏 ----
        sbar = ttk.Frame(self.root, padding=(10, 4))
        sbar.pack(fill='x')
        self.sv_status = tk.StringVar(value="✅ 就绪")
        self.sv_pos    = tk.StringVar(value="")
        ttk.Label(sbar, textvariable=self.sv_status).pack(side='left')
        ttk.Label(sbar, textvariable=self.sv_pos,
                  foreground='gray').pack(side='right')

    # ──────── Tab 1: 手动点击 ────────
    def _build_manual_tab(self, parent):
        row = 0
        parent.columnconfigure(0, weight=1)

        # ---- 点击位置 ----
        lf_pos = ttk.LabelFrame(parent, text="点击位置", padding=10)
        lf_pos.grid(row=row, column=0, sticky='ew', pady=(0, 8))
        row += 1

        f = ttk.Frame(lf_pos)
        f.pack(fill='x')
        ttk.Label(f, text="X:").pack(side='left')
        self.var_x = tk.IntVar(value=0)
        ttk.Spinbox(f, from_=0, to=9999, textvariable=self.var_x,
                     width=8).pack(side='left', padx=(0, 12))
        ttk.Label(f, text="Y:").pack(side='left')
        self.var_y = tk.IntVar(value=0)
        ttk.Spinbox(f, from_=0, to=9999, textvariable=self.var_y,
                     width=8).pack(side='left', padx=(0, 12))

        self.btn_pick = ttk.Button(f, text="📍 取点",
                                    command=self._pick_position)
        self.btn_pick.pack(side='left', padx=(0, 8))
        ttk.Button(f, text="📋 当前鼠标",
                   command=self._use_current_pos).pack(side='left')

        # ---- 点击设置 ----
        lf_set = ttk.LabelFrame(parent, text="点击设置", padding=10)
        lf_set.grid(row=row, column=0, sticky='ew', pady=(0, 8))
        row += 1

        # 点击类型
        f = ttk.Frame(lf_set); f.pack(fill='x', pady=3)
        ttk.Label(f, text="点击类型:", width=10,
                  anchor='e').pack(side='left')
        self.var_btn = tk.StringVar(value='left')
        for txt, val in [("左键", "left"), ("右键", "right"),
                         ("中键", "middle")]:
            ttk.Radiobutton(f, text=txt, variable=self.var_btn,
                            value=val).pack(side='left', padx=8)

        # 点击方式
        f = ttk.Frame(lf_set); f.pack(fill='x', pady=3)
        ttk.Label(f, text="点击方式:", width=10,
                  anchor='e').pack(side='left')
        self.var_click_type = tk.StringVar(value='single')
        for txt, val in [("单击", "single"), ("双击", "double")]:
            ttk.Radiobutton(f, text=txt, variable=self.var_click_type,
                            value=val).pack(side='left', padx=8)

        # 点击次数
        f = ttk.Frame(lf_set); f.pack(fill='x', pady=3)
        ttk.Label(f, text="点击次数:", width=10,
                  anchor='e').pack(side='left')
        self.var_count = tk.IntVar(value=1)
        ttk.Spinbox(f, from_=0, to=999999, textvariable=self.var_count,
                     width=10).pack(side='left')
        ttk.Label(f, text="(0 = 无限)",
                  foreground='gray').pack(side='left', padx=6)

        # 间隔时间
        f = ttk.Frame(lf_set); f.pack(fill='x', pady=3)
        ttk.Label(f, text="间隔时间:", width=10,
                  anchor='e').pack(side='left')
        self.var_interval = tk.IntVar(value=100)
        ttk.Spinbox(f, from_=1, to=999999, textvariable=self.var_interval,
                     width=10, increment=10).pack(side='left')
        ttk.Label(f, text="毫秒 (ms)",
                  foreground='gray').pack(side='left', padx=6)

        # 速度倍率
        f = ttk.Frame(lf_set); f.pack(fill='x', pady=3)
        ttk.Label(f, text="速度倍率:", width=10,
                  anchor='e').pack(side='left')
        self.var_speed = tk.DoubleVar(value=1.0)
        ttk.Scale(f, from_=0.1, to=10.0, variable=self.var_speed,
                  orient='horizontal', length=200).pack(side='left')
        self.lbl_speed = ttk.Label(f, text="1.0x", width=6)
        self.lbl_speed.pack(side='left', padx=4)
        self.var_speed.trace_add(
            'write',
            lambda *_: self.lbl_speed.config(
                text=f"{self.var_speed.get():.1f}x"
            )
        )

        # ---- 操作按钮 ----
        bf = ttk.Frame(parent)
        bf.grid(row=row, column=0, pady=10)
        row += 1

        self.btn_start = ttk.Button(bf, text="▶ 开始点击",
                                     command=self._start_click, width=16)
        self.btn_start.pack(side='left', padx=8)
        self.btn_stop = ttk.Button(bf, text="■ 停止",
                                    command=self._stop_click, width=16,
                                    state='disabled')
        self.btn_stop.pack(side='left', padx=8)

        # 进度
        self.sv_progress = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.sv_progress,
                  foreground='gray').grid(row=row, column=0)
        row += 1

    # ──────── Tab 2: 操作录制 ────────
    def _build_record_tab(self, parent):

        # ---- 录制控制 ----
        lf = ttk.LabelFrame(parent, text="录制控制", padding=10)
        lf.pack(fill='x', pady=(0, 8))

        bf = ttk.Frame(lf); bf.pack(fill='x')
        self.btn_rec_start = ttk.Button(bf, text="● 开始录制",
                                         command=self._start_rec, width=14)
        self.btn_rec_start.pack(side='left', padx=4)
        self.btn_rec_stop = ttk.Button(bf, text="■ 停止录制",
                                        command=self._stop_rec, width=14,
                                        state='disabled')
        self.btn_rec_stop.pack(side='left', padx=4)
        self.sv_rec_status = tk.StringVar(value="未录制")
        ttk.Label(bf, textvariable=self.sv_rec_status,
                  foreground='gray').pack(side='right')

        # ---- 事件列表 ----
        lf2 = ttk.LabelFrame(parent, text="录制事件", padding=10)
        lf2.pack(fill='both', expand=True, pady=(0, 8))

        cols = ('seq', 'type', 'pos', 'button', 'time')
        self.tree_events = ttk.Treeview(lf2, columns=cols,
                                         show='headings', height=8)
        self.tree_events.heading('seq',    text='#')
        self.tree_events.heading('type',   text='类型')
        self.tree_events.heading('pos',    text='位置')
        self.tree_events.heading('button', text='按键')
        self.tree_events.heading('time',   text='时间(s)')
        self.tree_events.column('seq',    width=40,  anchor='center')
        self.tree_events.column('type',   width=60,  anchor='center')
        self.tree_events.column('pos',    width=140, anchor='center')
        self.tree_events.column('button', width=60,  anchor='center')
        self.tree_events.column('time',   width=80,  anchor='center')

        sb = ttk.Scrollbar(lf2, orient='vertical',
                           command=self.tree_events.yview)
        self.tree_events.configure(yscrollcommand=sb.set)
        self.tree_events.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # ---- 复现与保存 ----
        lf3 = ttk.LabelFrame(parent, text="复现与保存", padding=10)
        lf3.pack(fill='x')

        # 速度
        f = ttk.Frame(lf3); f.pack(fill='x', pady=3)
        ttk.Label(f, text="复现速度:", width=10,
                  anchor='e').pack(side='left')
        self.var_play_speed = tk.DoubleVar(value=1.0)
        ttk.Scale(f, from_=0.1, to=10.0, variable=self.var_play_speed,
                  orient='horizontal', length=160).pack(side='left')
        self.lbl_play_speed = ttk.Label(f, text="1.0x", width=6)
        self.lbl_play_speed.pack(side='left', padx=4)
        self.var_play_speed.trace_add(
            'write',
            lambda *_: self.lbl_play_speed.config(
                text=f"{self.var_play_speed.get():.1f}x"
            )
        )
        self.var_loop = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="循环播放",
                        variable=self.var_loop).pack(side='left', padx=12)

        # 按钮
        bf2 = ttk.Frame(lf3); bf2.pack(fill='x', pady=(6, 0))
        self.btn_play = ttk.Button(bf2, text="▶ 复现",
                                    command=self._play_rec, width=12)
        self.btn_play.pack(side='left', padx=4)
        self.btn_stop_play = ttk.Button(bf2, text="■ 停止",
                                         command=self._stop_play_rec,
                                         width=12, state='disabled')
        self.btn_stop_play.pack(side='left', padx=4)

        # 保存
        sf = ttk.Frame(lf3); sf.pack(fill='x', pady=(8, 0))
        ttk.Label(sf, text="保存名称:").pack(side='left')
        self.var_save_name = tk.StringVar(
            value=f"录制_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        ttk.Entry(sf, textvariable=self.var_save_name,
                  width=28).pack(side='left', padx=4)
        ttk.Button(sf, text="💾 保存", command=self._save_rec,
                   width=8).pack(side='left', padx=4)

        self.sv_play_progress = tk.StringVar(value="")
        ttk.Label(lf3, textvariable=self.sv_play_progress,
                  foreground='gray').pack(anchor='w', pady=(4, 0))

    # ──────── Tab 3: 录制管理 ────────
    def _build_manage_tab(self, parent):

        # 工具栏
        tb = ttk.Frame(parent)
        tb.pack(fill='x', pady=(0, 8))
        ttk.Button(tb, text="🔄 刷新", command=self._refresh_list,
                   width=8).pack(side='left', padx=4)
        ttk.Button(tb, text="📂 打开文件夹", command=self._open_folder,
                   width=14).pack(side='left', padx=4)

        # 列表
        cols = ('name', 'count', 'duration', 'created')
        self.tree_files = ttk.Treeview(parent, columns=cols,
                                        show='headings', height=14)
        self.tree_files.heading('name',    text='名称')
        self.tree_files.heading('count',   text='事件数')
        self.tree_files.heading('duration', text='时长(s)')
        self.tree_files.heading('created', text='创建时间')
        self.tree_files.column('name',    width=200)
        self.tree_files.column('count',   width=70,  anchor='center')
        self.tree_files.column('duration', width=70,  anchor='center')
        self.tree_files.column('created', width=170)

        sb = ttk.Scrollbar(parent, orient='vertical',
                           command=self.tree_files.yview)
        self.tree_files.configure(yscrollcommand=sb.set)
        self.tree_files.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # 双击加载
        self.tree_files.bind('<Double-1>', lambda e: self._load_and_play())

        # 操作按钮
        bf = ttk.Frame(parent)
        bf.pack(fill='x', pady=(8, 0))
        ttk.Button(bf, text="▶ 加载并复现",
                   command=self._load_and_play, width=14).pack(
                       side='left', padx=4)
        ttk.Button(bf, text="✏️ 重命名",
                   command=self._rename_file, width=10).pack(
                       side='left', padx=4)
        ttk.Button(bf, text="🗑️ 删除",
                   command=self._delete_file, width=8).pack(
                       side='left', padx=4)

        self._recordings_cache = []
        self._refresh_list()

    # ════════════════ 手动点击逻辑 ════════════════

    def _use_current_pos(self):
        """获取当前鼠标位置并填入坐标框"""
        x, y = pyautogui.position()
        self.var_x.set(x)
        self.var_y.set(y)
        self.sv_status.set(f"✅ 已获取鼠标位置: ({x}, {y})")

    def _pick_position(self):
        """进入屏幕取点模式"""
        if self._picking:
            self._cancel_pick()
            return
        self._picking = True
        self.btn_pick.config(text="⏳ 点击屏幕取点...")
        self.sv_status.set("📍 请点击屏幕任意位置取点 (Esc 取消)")
        self.root.iconify()

        def _on_click(x, y, button, pressed):
            if pressed:
                self._picking = False
                self.root.after(0, lambda: self._finish_pick(int(x), int(y)))
                return False

        self._pick_ml = pynput_mouse.Listener(on_click=_on_click)
        self._pick_ml.start()

    def _finish_pick(self, x, y):
        """取点完成"""
        self.var_x.set(x)
        self.var_y.set(y)
        self.btn_pick.config(text="📍 取点")
        self.sv_status.set(f"✅ 取点成功: ({x}, {y})")
        self.root.deiconify()

    def _cancel_pick(self):
        """取消取点"""
        self._picking = False
        if self._pick_ml:
            self._pick_ml.stop()
            self._pick_ml = None
        self.btn_pick.config(text="📍 取点")
        self.sv_status.set("✅ 已取消取点")
        self.root.deiconify()

    def _start_click(self):
        """开始自动点击"""
        try:
            x        = self.var_x.get()
            y        = self.var_y.get()
            count    = self.var_count.get()
            interval = self.var_interval.get()
            button   = self.var_btn.get()
            speed    = self.var_speed.get()
            ctype    = self.var_click_type.get()
        except tk.TclError:
            messagebox.showwarning("参数错误", "请检查输入参数是否正确")
            return

        if interval < 1:
            messagebox.showwarning("参数错误", "间隔时间不能小于 1ms")
            return

        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.sv_status.set(f"🔄 点击中… 位置:({x},{y})")

        # 双击时每次执行2次 click，总次数按双倍计算
        actual_count = count * 2 if ctype == 'double' and count > 0 else count

        def on_progress(clicked, total):
            if ctype == 'double':
                display_clicked = clicked // 2
                display_total   = total // 2 if total > 0 else 0
                if total > 0:
                    self.sv_progress.set(
                        f"已双击: {display_clicked}/{display_total}"
                    )
                else:
                    self.sv_progress.set(f"已双击: {display_clicked} (无限)")
            else:
                if total > 0:
                    self.sv_progress.set(f"已点击: {clicked}/{total}")
                else:
                    self.sv_progress.set(f"已点击: {clicked} (无限)")

        def on_done(err):
            self.root.after(0, lambda: self._click_finished(err))

        if ctype == 'double':
            # 双击模式：每次循环执行两次 click
            self._start_double_click(
                x, y, count, interval, button, speed,
                on_progress, on_done
            )
        else:
            self.engine.start(x, y, actual_count, interval, button, speed,
                              on_progress, on_done)

    def _start_double_click(self, x, y, count, interval_ms, button, speed,
                            on_progress, on_done):
        """双击模式：每个间隔内快速执行两次点击"""
        with self.engine._lock:
            if self.engine._running:
                return
            self.engine._running = True

        def _loop():
            interval = max(interval_ms / 1000.0 / speed, 0.005)
            clicked = 0
            err = None
            try:
                while True:
                    with self.engine._lock:
                        if not self.engine._running:
                            break
                    if 0 < count <= clicked:
                        break
                    # 双击：快速两次
                    pyautogui.click(x=int(x), y=int(y), button=button)
                    time.sleep(0.01)
                    pyautogui.click(x=int(x), y=int(y), button=button)
                    clicked += 1
                    if on_progress:
                        try:
                            on_progress(clicked, count)
                        except Exception:
                            pass
                    if 0 < count <= clicked:
                        break
                    time.sleep(interval)
            except pyautogui.FailSafeException:
                err = "安全退出：鼠标已移至屏幕左上角"
            except Exception as e:
                err = str(e)
            finally:
                with self.engine._lock:
                    self.engine._running = False
                if on_done:
                    try:
                        on_done(err)
                    except Exception:
                        pass

        threading.Thread(target=_loop, daemon=True).start()

    def _click_finished(self, err):
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        if err:
            self.sv_status.set(f"⚠️ {err}")
            self.sv_progress.set("")
        else:
            self.sv_status.set("✅ 点击完成")
            self.sv_progress.set("")

    def _stop_click(self):
        self.engine.stop()
        self.sv_status.set("✅ 已停止点击")

    def _toggle_click(self):
        """F6 切换"""
        if self.engine.running:
            self._stop_click()
        else:
            self._start_click()

    # ════════════════ 录制逻辑 ════════════════

    def _start_rec(self):
        self.btn_rec_start.config(state='disabled')
        self.btn_rec_stop.config(state='normal')
        self.sv_rec_status.set("🔴 录制中…")
        for item in self.tree_events.get_children():
            self.tree_events.delete(item)

        def on_event(action, ev):
            if action == 'add':
                self.root.after(0, lambda: self._add_event_row(ev))

        self.recorder.start_recording(on_event)

    def _add_event_row(self, ev):
        seq = len(self.recorder.events)
        btn_cn = {'left': '左键', 'right': '右键',
                  'middle': '中键'}.get(ev.get('button', 'left'), '左键')
        self.tree_events.insert('', 'end', values=(
            seq, '点击', f"({ev['x']}, {ev['y']})", btn_cn,
            f"{ev['time']:.3f}"
        ))
        children = self.tree_events.get_children()
        if children:
            self.tree_events.see(children[-1])

    def _stop_rec(self):
        self.recorder.stop_recording()
        self.btn_rec_start.config(state='normal')
        self.btn_rec_stop.config(state='disabled')
        count = len(self.recorder.events)
        self.sv_rec_status.set(f"已录制 {count} 个事件")
        self.sv_status.set(f"✅ 录制完成，共 {count} 个事件")
        # 更新默认保存名
        self.var_save_name.set(
            f"录制_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    # ════════════════ 复现逻辑 ════════════════

    def _play_rec(self):
        events = self.recorder.events
        if not events:
            messagebox.showinfo("提示", "没有可复现的事件，请先录制")
            return
        self.btn_play.config(state='disabled')
        self.btn_stop_play.config(state='normal')
        self.sv_status.set("🔄 复现中…")

        def on_progress(i, total):
            self.sv_play_progress.set(f"复现进度: {i}/{total}")

        def on_done(err):
            self.root.after(0, lambda: self._play_finished(err))

        self.recorder.play(
            events=events,
            speed=self.var_play_speed.get(),
            loop=self.var_loop.get(),
            on_progress=on_progress,
            on_done=on_done
        )

    def _play_finished(self, err):
        self.btn_play.config(state='normal')
        self.btn_stop_play.config(state='disabled')
        self.sv_play_progress.set("")
        if err:
            self.sv_status.set(f"⚠️ {err}")
        else:
            self.sv_status.set("✅ 复现完成")

    def _stop_play_rec(self):
        self.recorder.stop_playback()
        self.sv_status.set("✅ 已停止复现")

    # ════════════════ 保存录制 ════════════════

    def _save_rec(self):
        if not self.recorder.events:
            messagebox.showinfo("提示", "没有可保存的事件")
            return
        name = self.var_save_name.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入保存名称")
            return
        path = self.recorder.save(name)
        if path:
            self.sv_status.set(f"✅ 已保存: {name}")
            self._refresh_list()
            messagebox.showinfo("保存成功", f"录制已保存到:\n{path}")
        else:
            messagebox.showerror("错误", "保存失败")

    # ════════════════ 录制管理 ════════════════

    def _refresh_list(self):
        for item in self.tree_files.get_children():
            self.tree_files.delete(item)
        self._recordings_cache = self.recorder.list_all()
        for rec in self._recordings_cache:
            created = (rec['created'][:19].replace('T', ' ')
                       if rec['created'] else '-')
            self.tree_files.insert(
                '', 'end', iid=rec['path'],
                values=(rec['name'], rec['count'],
                        f"{rec['duration']:.1f}", created)
            )

    def _open_folder(self):
        os.startfile(str(self.recorder.rec_dir))

    def _get_selected_rec(self):
        sel = self.tree_files.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条录制")
            return None
        path = sel[0]
        for rec in self._recordings_cache:
            if rec['path'] == path:
                return rec
        return None

    def _load_and_play(self):
        rec = self._get_selected_rec()
        if not rec:
            return
        if self.recorder.playing:
            messagebox.showinfo("提示", "正在复现中，请先停止")
            return

        events = rec['events']

        # 将事件加载到录制 Tab 的事件列表
        for item in self.tree_events.get_children():
            self.tree_events.delete(item)
        for i, ev in enumerate(events, 1):
            btn_cn = {'left': '左键', 'right': '右键',
                      'middle': '中键'}.get(ev.get('button', 'left'), '左键')
            self.tree_events.insert('', 'end', values=(
                i, '点击', f"({ev['x']}, {ev['y']})", btn_cn,
                f"{ev['time']:.3f}"
            ))

        # 开始复现
        self.btn_play.config(state='disabled')
        self.btn_stop_play.config(state='normal')
        self.sv_status.set(f"🔄 复现: {rec['name']}")

        def on_progress(i, total):
            self.sv_play_progress.set(f"复现进度: {i}/{total}")

        def on_done(err):
            self.root.after(0, lambda: self._play_finished(err))

        self.recorder.play(
            events=events,
            speed=self.var_play_speed.get(),
            loop=self.var_loop.get(),
            on_progress=on_progress,
            on_done=on_done
        )

    def _rename_file(self):
        rec = self._get_selected_rec()
        if not rec:
            return
        new_name = simpledialog.askstring(
            "重命名", "输入新名称:",
            initialvalue=rec['name'], parent=self.root
        )
        if new_name and new_name.strip():
            result = self.recorder.rename(rec['path'], new_name.strip())
            if result:
                self.sv_status.set(f"✅ 已重命名为: {new_name.strip()}")
                self._refresh_list()
            else:
                messagebox.showwarning("错误", "重命名失败（名称可能已存在）")

    def _delete_file(self):
        rec = self._get_selected_rec()
        if not rec:
            return
        if messagebox.askyesno("确认删除",
                               f"确定要删除录制「{rec['name']}」吗？"):
            if self.recorder.delete(rec['path']):
                self.sv_status.set(f"✅ 已删除: {rec['name']}")
                self._refresh_list()
            else:
                messagebox.showerror("错误", "删除失败")

    # ════════════════ 全局快捷键 ════════════════

    def _start_kb_listener(self):
        def on_press(key):
            try:
                if key == pynput_keyboard.Key.f6:
                    self.root.after(0, self._toggle_click)
                elif key == pynput_keyboard.Key.esc:
                    self.root.after(0, self._cancel_pick)
            except Exception:
                pass

        self._kb_l = pynput_keyboard.Listener(on_press=on_press)
        self._kb_l.start()

    # ════════════════ 鼠标位置追踪 ════════════════

    def _tick_pos(self):
        try:
            x, y = pyautogui.position()
            self.sv_pos.set(f"鼠标: ({x}, {y})")
        except Exception:
            pass
        self.root.after(200, self._tick_pos)

    # ════════════════ 退出 ════════════════

    def _quit(self):
        self.engine.stop()
        self.recorder.stop_recording()
        self.recorder.stop_playback()
        if self._pick_ml:
            self._pick_ml.stop()
        if self._kb_l:
            self._kb_l.stop()
        self.root.destroy()


# ═══════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    root = tk.Tk()
    app = AutoClickerApp(root)
    root.mainloop()
