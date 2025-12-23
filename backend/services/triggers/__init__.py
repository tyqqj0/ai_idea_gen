"""
触发层（Triggers）

不同入口（Docs add-on、事件回调、卡片回调等）负责把外部 payload 归一化为 ProcessContext，
并委托 TriggerService 统一完成：幂等、创建任务、启动后台处理、写入 TaskStore。
"""


