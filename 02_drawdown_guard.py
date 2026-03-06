"""
================================================================================
最大回撤监控与熔断器 (DrawdownGuard)
================================================================================

【TqSdk 简介】
TqSdk（天勤量化SDK）是由信易科技打造的专业期货量化交易开发框架，基于 Python 语言，
支持国内全品种期货、期权的实盘交易与历史回测。TqSdk 与天勤终端深度集成，提供
毫秒级行情推送、交易指令下达、账户资金管理等完整量化基础设施，是国内量化机构
和个人交易者广泛使用的开源量化框架之一。

TqSdk 通过订阅模式管理数据流：用户调用 `api.get_account()` 订阅账户资金快照，
每当账户净值（balance）、持仓盈亏（position_profit）、可用资金（available）等
字段发生变化时，TqSdk 的事件循环会触发数据更新，业务逻辑即可在 `wait_update()`
返回后立即获取最新状态，实现准实时风控监控。

TqSdk 官方文档：https://doc.shinnytech.com/tqsdk/latest/

--------------------------------------------------------------------------------
模块说明
--------------------------------------------------------------------------------
本模块实现了一个生产级最大回撤监控与自动熔断器（Circuit Breaker），
是期货量化交易中风险管理系统的核心组件。

【设计背景】
在量化交易中，策略失控（信号异常、市场极端行情、程序 bug 等）可能导致账户净值
在短时间内大幅缩水。传统人工监控存在反应迟缓的问题，而自动化熔断机制能够在
达到预设亏损阈值时立即触发：平掉所有仓位、暂停后续交易，从而保护账户安全。

【核心功能】
1. 双模式回撤监控：
   - 日内模式（intraday）：以当日开盘时的账户净值为基准，监控日内最大回撤
     适合单日频繁交易的高频/日内策略，防止当日爆仓
   - 累计模式（cumulative）：以历史最高净值（水位线/High-water Mark）为基准
     适合持仓周期较长的中低频趋势策略，防止总收益大幅回吐

2. 自动平仓熔断：触发阈值时自动遍历所有持仓，逐合约下市价平仓单

3. 交易暂停锁定：熔断后设置暂停标志，上层策略可通过 `is_trading_halted()` 
   方法检查是否允许继续交易，实现交易权限的软性控制

4. 熔断事件回调：支持注册自定义回调函数，熔断触发时同步调用
   （可用于发送告警通知、写日志、保存现场数据等）

5. 手动解除与重置：提供 `reset()` 方法允许手动解除熔断状态

【参数说明】
- max_drawdown_pct    : 最大回撤触发阈值（百分比），默认 5%（0.05）
- mode               : 监控模式，"intraday"（日内）或 "cumulative"（累计）
- close_positions    : 熔断时是否自动平仓，默认 True
- alert_drawdown_pct : 预警回撤比例，达到后发出警告但不熔断，默认 3%（0.03）

【线程安全】
本模块在单线程 TqSdk 事件循环中使用，不涉及多线程同步。

================================================================================
作者: AIGC Agent | 生成日期: 2026-03-02
版本: v1.0
================================================================================
"""

import logging
import time
from datetime import datetime, date
from typing import Callable, Dict, List, Optional, Literal

# TqSdk 核心导入
from tqsdk import TqApi, TqSim, TqAccount
from tqsdk.objs import Account, Position  # 账户/持仓数据对象

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DrawdownGuard")

# 熔断模式类型别名（Python 3.8+ 支持 Literal）
DrawdownMode = Literal["intraday", "cumulative"]


class DrawdownGuard:
    """
    最大回撤监控与熔断器

    实时监控账户净值变化，在账户回撤超过预设阈值时自动触发熔断机制：
    平掉所有持仓并暂停交易信号。支持日内回撤监控和累计高水位回撤监控两种模式。

    该类设计为"挂载式"风控组件，可无侵入式嵌入任意 TqSdk 策略的主循环中，
    只需在每次 wait_update 后调用 `check()` 方法即可完成回撤监控与熔断判断。

    参数
    ----
    api : TqApi
        TqSdk API 实例
    max_drawdown_pct : float
        最大回撤触发阈值（相对比例），例如 0.05 表示回撤 5% 时触发熔断
    mode : str
        监控模式：
        - "intraday"   : 日内模式，以当日初始净值为基准
        - "cumulative" : 累计模式，以历史最高净值（高水位）为基准
    close_positions : bool
        熔断时是否自动平掉所有持仓，默认 True
    alert_drawdown_pct : float
        预警阈值（相对比例），达到后输出警告但不触发熔断，默认 0.03
    symbols_filter : list of str, optional
        仅监控/平仓指定合约列表，为 None 时监控全部持仓
    on_breach_callback : callable, optional
        熔断触发时的回调函数，签名：callback(guard: DrawdownGuard) -> None
        可在此发送告警、记录日志等
    """

    def __init__(
        self,
        api: TqApi,
        max_drawdown_pct: float = 0.05,
        mode: DrawdownMode = "intraday",
        close_positions: bool = True,
        alert_drawdown_pct: float = 0.03,
        symbols_filter: Optional[List[str]] = None,
        on_breach_callback: Optional[Callable] = None,
    ):
        # ── 参数存储 ────────────────────────────────────────────────────────
        self.api = api
        self.max_drawdown_pct = max_drawdown_pct
        self.mode = mode
        self.close_positions = close_positions
        self.alert_drawdown_pct = alert_drawdown_pct
        self.symbols_filter = symbols_filter
        self.on_breach_callback = on_breach_callback

        # ── 账户订阅 ─────────────────────────────────────────────────────────
        # TqSdk 通过 get_account() 返回实时账户数据对象
        # 该对象会在 wait_update 后自动更新，无需手动轮询
        self._account: Account = api.get_account()

        # ── 内部状态变量 ─────────────────────────────────────────────────────
        # 熔断状态标志：True 表示已触发熔断，交易被暂停
        self._is_halted: bool = False

        # 初始净值基准（日内模式：当日开始时的净值）
        self._baseline_balance: Optional[float] = None

        # 历史最高净值（累计模式：高水位线 High-Water Mark）
        self._high_water_mark: Optional[float] = None

        # 当前最大回撤记录（用于监控与日志）
        self._current_max_drawdown: float = 0.0

        # 预警是否已触发（避免重复打印预警信息）
        self._alert_triggered: bool = False

        # 熔断触发时的时间戳与净值记录
        self._breach_time: Optional[datetime] = None
        self._breach_balance: Optional[float] = None
        self._breach_drawdown: Optional[float] = None

        # 日内模式：记录上次重置的日期（用于跨日自动重置基准）
        self._last_reset_date: Optional[date] = None

        # 回撤历史记录（最多保留最近100条，用于分析）
        self._drawdown_history: List[Dict] = []

        logger.info(
            f"DrawdownGuard 初始化 | 模式={mode} | "
            f"熔断阈值={max_drawdown_pct:.1%} | 预警阈值={alert_drawdown_pct:.1%} | "
            f"自动平仓={close_positions}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 属性访问
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def current_balance(self) -> float:
        """当前账户净值"""
        return self._account.balance

    @property
    def current_drawdown(self) -> float:
        """当前回撤比例（相对于基准净值）"""
        baseline = self._get_baseline()
        if baseline is None or baseline <= 0:
            return 0.0
        bal = self.current_balance
        return max(0.0, (baseline - bal) / baseline)

    # ──────────────────────────────────────────────────────────────────────────
    # 内部方法
    # ──────────────────────────────────────────────────────────────────────────

    def _get_baseline(self) -> Optional[float]:
        """
        根据监控模式返回回撤计算的基准净值

        - 日内模式：返回当日初始净值 _baseline_balance
        - 累计模式：返回历史最高净值 _high_water_mark
        """
        if self.mode == "intraday":
            return self._baseline_balance
        else:  # cumulative
            return self._high_water_mark

    def _initialize_baseline(self) -> bool:
        """
        初始化基准净值

        等待账户净值数据就绪后初始化基准。
        TqSdk 账户对象在首次 wait_update 前 balance 可能为 0，
        因此需要判断数据有效性。

        Returns
        -------
        bool
            True 表示初始化成功，False 表示数据未就绪
        """
        bal = self._account.balance
        if bal <= 0:
            # 账户数据尚未推送（TqSdk 连接初始化阶段）
            return False

        today = date.today()

        if self.mode == "intraday":
            # 日内模式：检查是否需要重置（跨日自动重置）
            if self._last_reset_date != today:
                self._baseline_balance = bal
                self._last_reset_date = today
                self._alert_triggered = False  # 跨日重置预警状态
                logger.info(
                    f"[日内模式] 基准净值已设置/重置 = {bal:,.2f}元 "
                    f"（{today}）"
                )
        else:
            # 累计模式：高水位只更新不降低
            if self._high_water_mark is None:
                self._high_water_mark = bal
                logger.info(f"[累计模式] 高水位初始化 = {bal:,.2f}元")
            elif bal > self._high_water_mark:
                prev = self._high_water_mark
                self._high_water_mark = bal
                logger.info(
                    f"[累计模式] 高水位更新: {prev:,.2f} → {bal:,.2f}元 "
                    f"(+{bal - prev:,.2f})"
                )

        return True

    def _close_all_positions(self) -> int:
        """
        平掉所有持仓（或 symbols_filter 中的持仓）

        遍历账户中所有合约持仓，分别对多头和空头持仓发出平仓委托。
        使用市价单（不传 limit_price）确保成交速度，降低冲击成本是次要考量，
        因为熔断时的核心目标是快速退出风险敞口。

        Returns
        -------
        int
            发出平仓委托的次数（每个方向算一次）
        """
        order_count = 0
        logger.warning("🔴 [熔断] 开始执行自动平仓程序...")

        # 获取账户下所有合约持仓字典
        # TqSdk 的 get_position 无参数时返回账户全部持仓快照
        try:
            positions = self.api.get_position()
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return 0

        for symbol, pos in positions.items():
            # 若设置了品种过滤器，跳过不在列表中的合约
            if self.symbols_filter and symbol not in self.symbols_filter:
                continue

            # 平多头持仓（volume_long > 0 表示有多头仓位）
            long_volume = getattr(pos, 'volume_long', 0) or 0
            if long_volume > 0:
                try:
                    # TqSdk 下单接口：不指定 limit_price 时为市价单
                    # offset="CLOSE" 平仓（TqSdk 自动处理平今/平昨）
                    self.api.insert_order(
                        symbol=symbol,
                        direction="SELL",       # 卖出平多
                        offset="CLOSE",         # 平仓
                        volume=long_volume,     # 全部多头手数
                    )
                    logger.warning(
                        f"  ✅ 平多仓 {symbol}: {long_volume}手（市价）"
                    )
                    order_count += 1
                except Exception as e:
                    logger.error(f"  ❌ 平多仓 {symbol} 失败: {e}")

            # 平空头持仓（volume_short > 0 表示有空头仓位）
            short_volume = getattr(pos, 'volume_short', 0) or 0
            if short_volume > 0:
                try:
                    self.api.insert_order(
                        symbol=symbol,
                        direction="BUY",        # 买入平空
                        offset="CLOSE",         # 平仓
                        volume=short_volume,    # 全部空头手数
                    )
                    logger.warning(
                        f"  ✅ 平空仓 {symbol}: {short_volume}手（市价）"
                    )
                    order_count += 1
                except Exception as e:
                    logger.error(f"  ❌ 平空仓 {symbol} 失败: {e}")

        if order_count == 0:
            logger.info("  ℹ️  当前无持仓需要平仓")

        return order_count

    def _trigger_breach(self, current_balance: float, drawdown: float):
        """
        触发熔断逻辑

        1. 设置熔断标志
        2. 记录熔断信息
        3. 自动平仓（若配置）
        4. 调用用户回调函数

        参数
        ----
        current_balance : float
            熔断触发时的账户净值
        drawdown : float
            当前回撤比例
        """
        self._is_halted = True
        self._breach_time = datetime.now()
        self._breach_balance = current_balance
        self._breach_drawdown = drawdown
        baseline = self._get_baseline()

        # ── 输出熔断告警日志 ──────────────────────────────────────────────────
        logger.critical(
            f"\n{'='*60}\n"
            f"🚨 【熔断器触发】\n"
            f"  时间     : {self._breach_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  监控模式 : {self.mode}\n"
            f"  基准净值 : {baseline:,.2f}元\n"
            f"  当前净值 : {current_balance:,.2f}元\n"
            f"  亏损金额 : {baseline - current_balance:,.2f}元\n"
            f"  回撤比例 : {drawdown:.2%}（阈值: {self.max_drawdown_pct:.2%}）\n"
            f"  自动平仓 : {'是' if self.close_positions else '否'}\n"
            f"{'='*60}"
        )

        # ── 执行自动平仓 ──────────────────────────────────────────────────────
        if self.close_positions:
            order_count = self._close_all_positions()
            logger.warning(f"[熔断] 共发出 {order_count} 笔平仓委托")

        # ── 调用用户自定义回调 ─────────────────────────────────────────────────
        if self.on_breach_callback:
            try:
                self.on_breach_callback(self)
            except Exception as e:
                logger.error(f"熔断回调函数执行异常: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # 核心公开接口
    # ──────────────────────────────────────────────────────────────────────────

    def check(self) -> bool:
        """
        执行回撤检查（主循环中每次 wait_update 后调用）

        此方法为非阻塞快速检查，通常在微秒级完成，不会影响主循环性能。

        执行流程：
        1. 初始化/更新净值基准
        2. 计算当前回撤比例
        3. 预警检查（达到预警阈值时输出警告）
        4. 熔断检查（达到熔断阈值时触发熔断流程）
        5. 更新回撤历史记录

        Returns
        -------
        bool
            True  : 账户状态正常，可以继续交易
            False : 已触发熔断，应停止发送新交易信号
        """
        # 已熔断状态：直接返回 False，不做重复处理
        if self._is_halted:
            return False

        # 初始化/更新基准净值
        if not self._initialize_baseline():
            # 数据未就绪（账户净值为0），跳过本次检查
            return True

        # 获取当前账户净值
        current_balance = self._account.balance
        baseline = self._get_baseline()

        if baseline is None or baseline <= 0:
            return True

        # 计算当前回撤比例
        drawdown = max(0.0, (baseline - current_balance) / baseline)

        # 更新最大回撤记录
        if drawdown > self._current_max_drawdown:
            self._current_max_drawdown = drawdown

        # 记录回撤快照（采样：回撤超过0.1%时记录，避免过于频繁）
        if drawdown > 0.001:
            snapshot = {
                "time": datetime.now().isoformat(),
                "balance": current_balance,
                "baseline": baseline,
                "drawdown": drawdown,
            }
            self._drawdown_history.append(snapshot)
            # 保留最近100条记录，防止内存无限增长
            if len(self._drawdown_history) > 100:
                self._drawdown_history.pop(0)

        # ── 预警检查 ──────────────────────────────────────────────────────────
        # 达到预警阈值但未到熔断阈值时输出告警（每次只输出一次，避免刷屏）
        if drawdown >= self.alert_drawdown_pct and not self._alert_triggered:
            self._alert_triggered = True
            logger.warning(
                f"⚠️  [回撤预警] 当前回撤 {drawdown:.2%} 已达预警阈值 "
                f"{self.alert_drawdown_pct:.2%} | "
                f"基准={baseline:,.0f} 当前={current_balance:,.0f}"
            )
        elif drawdown < self.alert_drawdown_pct * 0.8:
            # 回撤缓和时重置预警标志（给予20%缓冲，避免频繁切换）
            self._alert_triggered = False

        # ── 熔断检查 ──────────────────────────────────────────────────────────
        if drawdown >= self.max_drawdown_pct:
            self._trigger_breach(current_balance, drawdown)
            return False

        return True

    def is_trading_halted(self) -> bool:
        """
        查询当前交易是否被熔断暂停

        上层策略在下单前应先调用此方法检查是否允许交易：
          if not guard.is_trading_halted():
              api.insert_order(...)

        Returns
        -------
        bool
            True  : 交易已被暂停（熔断触发）
            False : 交易状态正常
        """
        return self._is_halted

    def reset(self, new_baseline: Optional[float] = None):
        """
        手动重置熔断器状态

        在人工确认风险已解除后，可调用此方法解除熔断锁定，恢复交易权限。
        建议重置前人工确认市场风险已消退，不应在自动化逻辑中无条件重置。

        参数
        ----
        new_baseline : float, optional
            重置后的基准净值；为 None 时使用当前账户净值作为新基准
        """
        old_state = self._is_halted
        self._is_halted = False
        self._alert_triggered = False
        self._current_max_drawdown = 0.0

        # 更新基准净值
        current_bal = self._account.balance
        new_base = new_baseline if new_baseline and new_baseline > 0 else current_bal

        if self.mode == "intraday":
            self._baseline_balance = new_base
        else:
            # 累计模式重置时，高水位更新为当前净值（不能低于当前净值）
            self._high_water_mark = max(new_base, current_bal)

        logger.info(
            f"[熔断器] 状态已重置 | "
            f"原状态={'熔断' if old_state else '正常'} → 正常 | "
            f"新基准净值={new_base:,.2f}元"
        )

    def get_status(self) -> Dict:
        """
        获取熔断器当前状态信息（用于监控面板或日志）

        Returns
        -------
        dict
            包含熔断器各项状态指标的字典
        """
        baseline = self._get_baseline()
        current_bal = self._account.balance
        drawdown = self.current_drawdown

        status = {
            "is_halted": self._is_halted,
            "mode": self.mode,
            "current_balance": current_bal,
            "baseline": baseline,
            "current_drawdown_pct": drawdown,
            "max_drawdown_pct": self._current_max_drawdown,
            "alert_threshold": self.alert_drawdown_pct,
            "breach_threshold": self.max_drawdown_pct,
            "alert_triggered": self._alert_triggered,
        }

        if self._is_halted:
            status["breach_time"] = (
                self._breach_time.isoformat() if self._breach_time else None
            )
            status["breach_balance"] = self._breach_balance
            status["breach_drawdown_pct"] = self._breach_drawdown

        return status


# ══════════════════════════════════════════════════════════════════════════════
# 使用示例
# ══════════════════════════════════════════════════════════════════════════════

def on_drawdown_breach(guard: DrawdownGuard):
    """
    熔断触发回调函数示例

    在实际生产环境中，可在此处：
    - 发送微信/钉钉/邮件告警通知
    - 写入告警数据库
    - 保存当时的策略状态快照
    - 触发运维流程
    """
    status = guard.get_status()
    breach_dd = status.get("breach_drawdown_pct", 0)
    print(
        f"\n📱 [告警通知] DrawdownGuard 熔断触发！\n"
        f"  净值: {status['current_balance']:,.2f}元\n"
        f"  回撤: {breach_dd:.2%}\n"
        f"  时间: {status.get('breach_time', 'N/A')}\n"
        f"请立即检查策略状态！"
    )
    # 实际场景可在此调用推送 API，例如：
    # send_wechat_alert(msg=f"熔断触发！回撤={breach_dd:.2%}")
    # send_dingtalk_alert(...)


def example_main():
    """
    完整使用示例：将 DrawdownGuard 集成到 TqSdk 策略主循环中

    本示例演示两种典型集成方式：
    方式A：日内最大回撤监控（适合日内高频策略）
    方式B：累计高水位回撤监控（适合趋势跟踪策略）
    """
    # ── 创建 TqSdk API 实例 ───────────────────────────────────────────────────
    # 实盘替换为：
    #   api = TqApi(TqAccount("BROKER", "ACCOUNT", "PASSWORD"), auth=TqAuth("用户名","密码"))
    api = TqApi(TqSim(), auth=None)  # 示例用模拟账户

    # ── 方式A：日内模式（监控当日回撤，超过5%熔断） ────────────────────────
    guard_intraday = DrawdownGuard(
        api=api,
        max_drawdown_pct=0.05,          # 熔断阈值：日内回撤 5%
        mode="intraday",                # 日内模式
        close_positions=True,           # 熔断时自动平仓
        alert_drawdown_pct=0.03,        # 预警阈值：日内回撤 3%
        on_breach_callback=on_drawdown_breach,  # 熔断回调
    )

    # ── 方式B：累计模式（监控历史高点回撤，超过15%熔断） ─────────────────
    guard_cumulative = DrawdownGuard(
        api=api,
        max_drawdown_pct=0.15,          # 熔断阈值：净值从高点回撤 15%
        mode="cumulative",              # 累计高水位模式
        close_positions=True,
        alert_drawdown_pct=0.08,        # 预警：回撤 8% 发出告警
        on_breach_callback=on_drawdown_breach,
    )

    # 选择使用哪种模式（此处使用日内模式演示）
    guard = guard_intraday

    # ── 订阅行情（策略需要的交易品种） ───────────────────────────────────────
    SYMBOL = "SHFE.rb2501"
    quote = api.get_quote(SYMBOL)

    print(f"{'='*60}")
    print(f"DrawdownGuard 运行示例（模式: {guard.mode}）")
    print(f"熔断阈值: {guard.max_drawdown_pct:.1%} | 预警: {guard.alert_drawdown_pct:.1%}")
    print(f"{'='*60}\n")

    check_counter = 0  # 检查计数器（用于演示）

    # ── 主事件循环 ────────────────────────────────────────────────────────────
    # TqSdk 的 wait_update() 是事件驱动核心，阻塞等待任意订阅数据的更新
    # 每次返回后代表有新的行情、账户或持仓数据到来
    while True:
        api.wait_update()
        check_counter += 1

        # ─────────────────────────────────────────────────────────────────────
        #        # 核心集成点：每次行情/账户更新后执行回撤检查
        # check() 返回 True 表示可以正常交易，False 表示已熔断
        # ─────────────────────────────────────────────────────────────────────
        can_trade = guard.check()

        if not can_trade:
            # 熔断状态：不发出新的交易信号，等待人工干预
            if check_counter % 300 == 0:  # 每300次循环打印一次状态（避免刷屏）
                status = guard.get_status()
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"⛔ 交易已暂停 | "
                    f"熔断时间: {status.get('breach_time', 'N/A')} | "
                    f"熔断时净值: {status.get('breach_balance', 0):,.0f}元"
                )
            continue  # 跳过交易逻辑，等待人工重置

        # ── 账户信息监控输出（每500次循环打印一次） ──────────────────────────
        if check_counter % 500 == 0:
            status = guard.get_status()
            baseline = status["baseline"] or 0
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"净值={status['current_balance']:,.0f}元 | "
                f"基准={baseline:,.0f}元 | "
                f"当前回撤={status['current_drawdown_pct']:.2%} | "
                f"最大回撤={status['max_drawdown_pct']:.2%}"
            )

        # ── 此处放置正常交易逻辑 ──────────────────────────────────────────────
        # 只有 can_trade == True 时才会执行到此处，保证熔断后不再下单
        # 示例：
        # if api.is_changing(quote, "last_price"):
        #     if 开仓信号:
        #         api.insert_order(SYMBOL, "BUY", "OPEN", volume=1)


if __name__ == "__main__":
    example_main()
