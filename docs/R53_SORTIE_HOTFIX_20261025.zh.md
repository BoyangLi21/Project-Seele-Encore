# R53 排液/出击热修复断点（2026-10-25）

用户反馈：待机时灰色转移架错误出现，插栓演出异常，实际远程服务器出击时 LCL 不下降。

- 旧 1.0.1 JAR 是仅客户端显示候选，不是排液/出击修复；未交付为已验证修复，不要用于服务端。
- 已确认客户端渲染 parked 判断错误排除了 shallowBay/supportOnly；源代码移除了该排除。显示候选仍未完成实际画面验收。
- 实际 R53 服务端使用 NervAssemblyOwnerR52.prepareOriginal。DRAIN 同步推进排液与 acceptCarrierActuatorR52；升架返回 WAITING 时 PrepareTicks 不增加。仅隐藏客户端转移架无法解除这一阻塞。
- 服务端实际停点尚未知：INSERT、SEAL、DRAIN 及原编队/设备条件均可能等待，未拿到远程现场证据前不指定某一个为已确认根因，不绕过身份/碰撞条件硬推进。
- 用户确认服务器在另一台机器；本机仅 PCL 远程客户端，不能读取远程运行时。下一步需要服务器 logs/latest.log 与当前世界 projectseele_nerv_routes_r52.dat，或当前世界副本，以便定点读取 Prepare/PrepareTicks/DrainedLayers 并做小补丁。
- 本次不重打 PCL/服务器整包，不重置原机或覆盖存档；修复交付须说明客户端/服务端分别安装什么。
- 冬月等 staff 默认 Invulnerable，但 R53 maintainOriginalStaff 不会重建死亡/删除实体。恢复应沿用当前 ROOT_MECHANICAL_OWNER.json 中的原 UUID、StaffId 与岗位，不能普通召唤无身份的新职员冒充原岗位。