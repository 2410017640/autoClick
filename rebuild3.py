# -*- coding: utf-8 -*-
# 重写 Git 历史提交信息（使用 git commit --amend）
import subprocess, os

os.chdir(r'D:\IDEA\works\test\autoClick')

commits = [
    ('7fe7c66', '初始版本：支持拖动的 AutoClicker Pro'),
    ('ac86b6f', '修复录制器新增拖动检测（按下-移动-释放）'),
    ('5ef0954', '修复拖动事件在录制 UI 中显示 + 添加键盘录制选项'),
    ('0d09fb4', '添加可自定义快捷键设置，支持持久化配置和冲突检测'),
    ('78b790a', '录制和回放时自动最小化主窗口，防止遮挡点击目标'),
    ('5009773', '添加分辨率感知录制和回放，自动缩放坐标适配不同 DPI'),
    ('66e6336', '修复 _start_rec 中 cur_w/cur_h 未定义的 NameError'),
    ('c5ac0ae', '添加完整鼠标轨迹录制，每 50ms 采样位置，回放时用 pyautogui.moveTo 复现'),
    ('2cb836d', '修复 _load_and_play 中 move/key/drag 事件 KeyError，添加事件列表删除和延迟编辑列'),
    ('0b2c0ab', '将删除列替换为编辑列，增加延迟编辑弹窗和删除按钮'),
    ('517957c', '修复编辑列点击事件 - identify_column 返回 #N 格式'),
    ('4e9ebea', '修复编辑弹窗中删除事件后 IndexError，删除后自动关闭弹窗，按钮改为中文'),
]

env = os.environ.copy()

for sha, msg in commits:
    r = subprocess.run(['git', 'reset', '--hard', sha],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:
        print('FAIL reset ' + sha)
        continue
    r2 = subprocess.run(['git', 'commit', '--amend', '-m', msg], env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r2.returncode != 0:
        print('FAIL amend ' + sha[:7] + ' | ' + msg)
    else:
        print('OK ' + sha[:7] + ' | ' + msg)

print('\nFinal log:')
subprocess.run(['git', 'log', '--oneline'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)