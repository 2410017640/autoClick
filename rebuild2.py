# -*- coding: utf-8 -*-
import subprocess, shutil, os, binascii, hashlib, zlib

os.chdir(r'D:\IDEA\works\test\autoClick')

# 目标提交链和中文消息
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

# 解析 Git 对象，替换 commit message，返回新 SHA
def rewrite_commit(old_sha, new_msg):
    # 读取原 commit 对象
    raw = subprocess.check_output(['git', 'cat-file', '-p', old_sha])
    text = raw.decode('utf-8', errors='replace')

    # 解析 tree 和 parent
    lines = text.split('\n')
    tree_sha = None
    parent_sha = None
    author_line = None
    committer_line = None
    msg_lines = []
    phase = 'header'
    for line in lines:
        if phase == 'header':
            if line.startswith('tree '):
                tree_sha = line[5:]
            elif line.startswith('parent '):
                parent_sha = line[7:]
            elif line.startswith('author '):
                author_line = line
            elif line.startswith('committer '):
                committer_line = line
            elif line == '':
                phase = 'message'
        elif phase == 'message':
            msg_lines.append(line)

    new_msg_bytes = ('%s\n' % new_msg).encode('utf-8')
    new_text = 'tree %s\n' % tree_sha
    if parent_sha:
        new_text += 'parent %s\n' % parent_sha
    new_text += '%s\n%s\n\n' % (author_line, committer_line)
    new_text += new_msg.decode('utf-8')

    # 写入新对象（计算新 SHA）
    new_raw = new_text.encode('utf-8')
    sha_obj = hashlib.sha1(b'commit %d\0' % len(new_raw)).hexdigest()
    dir1 = sha_obj[:2]
    dir2 = sha_obj[2:]

    obj_dir = os.path.join('.git', 'objects', dir1)
    if not os.path.exists(obj_dir):
        os.makedirs(obj_dir)
    obj_path = os.path.join(obj_dir, dir2)
    compressed = zlib.compress(new_raw)
    with open(obj_path, 'wb') as f:
        f.write(compressed)

    return sha_obj

# 收集所有需要的 tree SHA（按顺序）
all_shas = []
prev = None
for sha, msg in commits:
    raw = subprocess.check_output(['git', 'cat-file', '-p', sha])
    lines = raw.decode('utf-8', errors='replace').split('\n')
    tree_sha = None
    parent_sha = None
    for line in lines:
        if line.startswith('tree '):
            tree_sha = line[5:]
        elif line.startswith('parent '):
            parent_sha = line[7:]
    all_shas.append((sha, msg, tree_sha, parent_sha))

# 从第一个提交之前开始重建
subprocess.run(['git', 'reset', '--hard', '7fe7c66~'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

new_chain = []
for i, (old_sha, msg, tree_sha, parent_old) in enumerate(all_shas):
    # 确定 parent（上一个新提交）
    parent = '7fe7c66~'
    if i > 0:
        parent = new_chain[-1]

    # 从原 commit 对象中提取 author/committer 时间戳
    raw = subprocess.check_output(['git', 'cat-file', '-p', old_sha])
    text = raw.decode('utf-8', errors='replace')
    author_line = None
    committer_line = None
    for line in text.split('\n'):
        if line.startswith('author '):
            author_line = line
        elif line.startswith('committer '):
            committer_line = line

    # 构建新 commit
    new_text = 'tree %s\n' % tree_sha
    new_text += 'parent %s\n' % parent
    new_text += '%s\n%s\n\n%s\n' % (author_line, committer_line, msg)

    new_raw = new_text.encode('utf-8')
    new_sha = hashlib.sha1(b'commit %d\0' % len(new_raw) + new_raw).hexdigest()

    # 写入新对象
    dir1 = new_sha[:2]
    dir2 = new_sha[2:]
    obj_dir = os.path.join('.git', 'objects', dir1)
    if not os.path.exists(obj_dir):
        os.makedirs(obj_dir)
    obj_path = os.path.join(obj_dir, dir2)
    with open(obj_path, 'wb') as f:
        f.write(zlib.compress(new_raw))

    new_chain.append(new_sha)
    print('New commit %s | %s' % (new_sha[:7], msg))

# 更新 master 分支到最新提交
with open(os.path.join('.git', 'refs', 'heads', 'master'), 'w') as f:
    f.write(new_chain[-1] + '\n')

print('\nDone!')
subprocess.run(['git', 'log', '--oneline'],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)