# 核心模块提取计划

## 目标
将 autoclicker.py 和 autoclicker_pro.py 中的重复代码提取为共享模块

## 需要提取的类

### 1. ClickEngine (点击引擎)
**位置**: 
- autoclicker.py: 第60-132行
- autoclicker_pro.py: 第524-589行

**操作**: 完全相同，提取到 `core/click_engine.py`

### 2. Recorder (录制器)
**位置**:
- autoclicker.py: 第137-327行
- autoclicker_pro.py: 第594-780行

**操作**: 完全相同，提取到 `core/recorder.py`

### 3. FlowStep, FlowProject, FlowEngine (流程相关)
**位置**: 
- 仅在 autoclicker_pro.py: 第116-519行

**操作**: 移动到 `core/flow_engine.py`

### 4. StepEditDialog, FlowCanvas (UI组件)
**位置**:
- 仅在 autoclicker_pro.py: 第785-1809行

**操作**: 移动到 `ui/advanced_ui.py`

## 新目录结构

```
autoClick/
├── core/                      # 新增: 核心逻辑
│   ├── __init__.py
│   ├── click_engine.py       # 点击引擎
│   ├── recorder.py           # 录制器
│   └── flow_engine.py        # 流程引擎 (Pro专用)
├── ui/                        # 新增: UI组件
│   ├── __init__.py
│   └── advanced_ui.py        # 高级UI (Pro专用)
├── recordings/               # 录制文件存储
├── autoclicker.py            # 轻量版 (导入 core.*)
├── autoclicker_pro.py        # 专业版 (导入 core.*, ui.*)
├── requirements.txt
├── 启动连点器.bat
├── 启动连点器Pro.bat
└── OPTIMIZATION_REPORT.md
```

## 迁移步骤

### Step 1: 创建 core 模块
1. 创建 `core/__init__.py`
2. 复制 ClickEngine 到 `core/click_engine.py`
3. 复制 Recorder 到 `core/recorder.py`
4. 复制 Flow* 类到 `core/flow_engine.py`

### Step 2: 创建 ui 模块
1. 创建 `ui/__init__.py`
2. 复制 StepEditDialog 和 FlowCanvas 到 `ui/advanced_ui.py`

### Step 3: 修改导入
**autoclicker.py**:
```python
# 修改前
class ClickEngine:
    ...

class Recorder:
    ...

# 修改后
from core.click_engine import ClickEngine
from core.recorder import Recorder
```

**autoclicker_pro.py**:
```python
# 修改前
class ClickEngine:
    ...

class Recorder:
    ...

class FlowStep:
    ...

# 修改后
from core.click_engine import ClickEngine
from core.recorder import Recorder
from core.flow_engine import FlowStep, FlowProject, FlowEngine
from ui.advanced_ui import StepEditDialog, FlowCanvas
```

### Step 4: 测试验证
1. 运行基础版: `python autoclicker.py`
2. 运行专业版: `python autoclicker_pro.py`
3. 验证所有功能正常

## 预期收益

### 代码量减少
- **当前总行数**: ~3900 行
- **重复代码**: ~1200 行 (30%)
- **优化后**: ~2700 行
- **减少比例**: **~30%**

### 维护成本
- **Bug修复**: 只需修改一处
- **功能更新**: 自动同步到两个版本
- **代码审查**: 更清晰的职责划分

### 可扩展性
- 轻松添加新版本 (如: autoclicker_lite.py)
- 核心逻辑独立测试
- UI 可替换 (未来可支持 PyQt/Web)
