"""
================================================================================
ATR动态仓位管理器 (AtrPositionSizer)
================================================================================

【TqSdk 简介】
TqSdk（天勤量化SDK）是由信易科技自主研发、面向专业量化交易者的开源 Python SDK。
它直接对接天勤终端行情与交易系统，支持国内期货、期权的实盘与回测。TqSdk 提供
tick/K线订阅、账户信息查询、下单/撤单/持仓管理等完整功能接口，并内置多账户、
多品种并发框架，极大降低了量化策略开发的门槛。

TqSdk 的核心理念是"同步即异步"：通过 `api.wait_update()` 轮询事件驱动模型，
开发者以同步代码风格即可实现高并发、低延迟的量化策略，无需手动处理线程或回调地狱。

TqSdk 官方文档：https://doc.shinnytech.com/tqsdk/latest/

--------------------------------------------------------------------------------
模块说明
--------------------------------------------------------------------------------
本模块实现了一个基于 ATR（Average True Range，平均真实波幅）的动态仓位管理器。

【设计思路】
在期货量化交易中，固定手数下单忽视了市场波动率的差异，导致低波动期风险偏小、
高波动期风险超出预期。ATR 是衡量市场波动的经典技术指标，其值越大代表市场越
剧烈，单次价格变动风险越高。

AtrPositionSizer 通过以下逻辑动态调节仓位：
  1. 计算 N 周期 ATR 作为当前波动率基准
  2. 根据账户净值与每笔最大亏损比例（risk_per_trade）推算出"可承受的最大金额损失"
  3. 将该金额除以 (ATR × 合约乘数) 得到建议手数
  4. 对最终手数做上下边界约束（min_lots / max_lots）

这样，当市场波动剧烈时仓位自动缩小，平静时仓位适当放大，始终将单次风险控制
在总资产的固定比例内，是期货量化中最成熟、最被机构广泛使用的仓位管理方法之一。

【参数说明】
- symbol         : 期货合约代码，如 "SHFE.rb2410"
- atr_period     : ATR 计算周期，默认 14 根 K 线
- risk_per_trade : 每笔交易最大风险占账户净值比例，默认 1%（0.01）
- min_lots       : 仓位下界（手），默认 1
- max_lots       : 仓位上界（手），默认 20

【适用场景】
- 趋势跟随策略中的动态仓位分配
- 组合策略中各品种仓位权重均衡
- 止损点位已知时精确计算仓位

【使用方式】
本类设计为无状态可复用工具类，可被任意 TqSdk 策略 import 并实例化，
不依赖特定策略逻辑，与账户交易逻辑解耦。

================================================================================
作者: AIGC Agent | 生成日期: 2026-03-02
版本: v1.0
================================================================================
"""

import math
import logging
from typing import Optional

# TqSdk 核心导入
# TqApi      : 主 API 对象，所有行情/交易操作的入口
# TqSim      : 模拟账户，用于回测与模拟交易（实盘替换为 TqAccount）
# TqKq       : 快期模拟账户（可选）
from tqsdk import TqApi, TqSim, TqAccount
from tqsdk.objs import Quote  # 行情快照对象（含最新价、涨跌停等字段）

# 配置日志，方便策略运行时追踪仓位计算过程
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AtrPositionSizer")


class AtrPositionSizer:
    """
    ATR动态仓位管理器

    根据市场当前波动率（ATR）与账户净值动态计算每笔交易的建议仓位（手数）。
    实现了"固定风险比例"仓位管理方法，确保每笔交易的预期最大亏损始终是账户
    净值的固定百分比。

    该类是一个纯计算工具，不执行下单操作，仅返回建议手数供上层策略使用。
    设计为无状态可复用组件，可在多品种策略中分别实例化。

    参数
    ----
    api : TqApi
        TqSdk API 实例，用于订阅 K 线行情
    symbol : str
        期货合约代码，例如 "SHFE.rb2410"（上期所螺纹钢2410合约）
    atr_period : int
        ATR 计算所用 K 线根数，默认 14
    risk_per_trade : float
        每笔交易允许亏损的账户净值比例，默认 0.01（即 1%）
    multiplier : float
        合约乘数（每手对应的标的数量），默认自动从行情获取
        若无法自动获取则需手动传入，例如螺纹钢为 10
    min_lots : int
        最小仓位手数限制，默认 1
    max_lots : int
        最大仓位手数限制，默认 20
    kline_duration_seconds : int
        K 线周期（秒），默认 3600（1小时线）
    """

    def __init__(
        self,
        api: TqApi,
        symbol: str,
        atr_period: int = 14,
        risk_per_trade: float = 0.01,
        multiplier: Optional[float] = None,
        min_lots: int = 1,
        max_lots: int = 20,
        kline_duration_seconds: int = 3600,
    ):
        # ── 参数存储 ────────────────────────────────────────────────────────
        self.api = api
        self.symbol = symbol
        self.atr_period = atr_period
        self.risk_per_trade = risk_per_trade
        self.min_lots = min_lots
        self.max_lots = max_lots
        self.kline_duration_seconds = kline_duration_seconds

        # ── 获取合约信息 ─────────────────────────────────────────────────────
        # quote 对象包含合约的基础信息，如 volume_multiple（合约乘数）、price_tick 等
        self._quote: Quote = api.get_quote(symbol)

        # 合约乘数：若用户未手动传入，则自动从行情对象读取
        # volume_multiple 表示每手合约对应的标的数量
        # 例如：螺纹钢 RB 每手=10吨，铜 CU 每手=5吨，原油 SC 每手=1000桶
        if multiplier is not None:
            self.multiplier = multiplier
        else:
            # 等待行情就绪后读取（首次调用 get_lots 时会自动就绪）
            self.multiplier = None  # 延迟初始化

        # ── 订阅 K 线数据 ────────────────────────────────────────────────────
        # TqSdk 通过 get_kline_serial 订阅 K 线序列
        # 参数：合约代码、K线周期（秒）、K线数量
        # 返回 DataFrame 格式，字段包含 open/high/low/close/volume/open_oi 等
        # 注意：K线数量需大于 ATR 周期，否则计算结果会有 NaN
        self._klines = api.get_kline_serial(
            symbol,
            duration_seconds=kline_duration_seconds,
            data_length=atr_period + 50,  # 额外缓冲确保足够数据量
        )

        logger.info(
            f"[{symbol}] AtrPositionSizer 初始化完成 | "
            f"ATR周期={atr_period} | 风险比例={risk_per_trade:.2%} | "
            f"仓位范围=[{min_lots}, {max_lots}]手"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # 内部计算方法
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_atr(self) -> Optional[float]:
        """
        计算当前 ATR 值（Wilder's Smoothed ATR）

        True Range (TR) 定义：
          TR = max(
               high - low,             # 当日振幅
               |high - prev_close|,    # 跳空高开幅度
               |low  - prev_close|     # 跳空低开幅度
          )
        ATR = TR 的 N 期指数移动平均（Wilder's smoothing，等价于 EMA(alpha=1/N)）

        Returns
        -------
        float or None
            当前 ATR 值；若 K 线数据不足则返回 None
        """
        klines = self._klines

        # 确保有足够数据量（至少需要 atr_period + 1 根 K 线才能计算）
        if len(klines) < self.atr_period + 1:
            logger.warning(
                f"[{self.symbol}] K线数据不足 ({len(klines)} < {self.atr_period + 1})，"
                f"无法计算 ATR"
            )
            return None

        # 取最近的数据切片（避免对全量数据操作，提升性能）
        recent = klines.iloc[-(self.atr_period + 1):]

        highs  = recent["high"].values    # 最高价序列
        lows   = recent["low"].values     # 最低价序列
        closes = recent["close"].values   # 收盘价序列

        # 逐根计算 True Range
        tr_values = []
        for i in range(1, len(recent)):
            prev_close = closes[i - 1]
            high = highs[i]
            low  = lows[i]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low  - prev_close),
            )
            tr_values.append(tr)

        if not tr_values:
            return None

        # Wilder's 平滑 ATR：首值为简单均值，后续迭代平滑
        # atr_t = atr_{t-1} * (N-1)/N + TR_t * (1/N)
        atr = sum(tr_values[:self.atr_period]) / self.atr_period
        for tr in tr_values[self.atr_period:]:
            atr = atr * (self.atr_period - 1) / self.atr_period + tr / self.atr_period

        logger.debug(f"[{self.symbol}] ATR({self.atr_period}) = {atr:.4f}")
        return atr

    def _get_multiplier(self) -> float:
        """
        获取合约乘数（延迟初始化）

        TqSdk 的 quote 对象在 wait_update 后才会有完整数据，
        因此合约乘数采用延迟初始化方式，在首次需要时读取。

        Returns
        -------
        float
            合约乘数；若无法获取则返回默认值 1.0
        """
        if self.multiplier is not None:
            return self.multiplier

        # 从行情快照读取合约乘数
        vm = getattr(self._quote, "volume_multiple", None)
        if vm and vm > 0:
            self.multiplier = float(vm)
            logger.info(f"[{self.symbol}] 自动获取合约乘数: {self.multiplier}")
        else:
            # 无法获取时默认为1，调用方应手动传入
            logger.warning(
                f"[{self.symbol}] 无法从行情获取合约乘数，使用默认值 1.0，"
                f"建议手动传入 multiplier 参数"
            )
            self.multiplier = 1.0

        return self.multiplier

    # ──────────────────────────────────────────────────────────────────────────
    # 核心公开接口
    # ──────────────────────────────────────────────────────────────────────────

    def get_lots(
        self,
        account_balance: float,
        stop_loss_atr_multiple: float = 2.0,
        custom_stop_loss_price: Optional[float] = None,
        entry_price: Optional[float] = None,
    ) -> int:
        """
        根据当前 ATR 与账户净值计算建议仓位（手数）

        仓位计算公式：
          max_risk_amount = account_balance × risk_per_trade
          atr_stop_distance = ATR × stop_loss_atr_multiple （ATR止损距离）
          raw_lots = max_risk_amount / (atr_stop_distance × multiplier)
          lots = clamp(floor(raw_lots), min_lots, max_lots)

        若指定了 custom_stop_loss_price 与 entry_price，则直接用价差替代 ATR止损距离：
          price_stop_distance = |entry_price - custom_stop_loss_price|
          raw_lots = max_risk_amount / (price_stop_distance × multiplier)

        参数
        ----
        account_balance : float
            当前账户净值（元），通常取 account.balance 或 account.static_balance
        stop_loss_atr_multiple : float
            止损距离 = ATR × 该倍数，默认 2.0（即2倍ATR止损）
        custom_stop_loss_price : float, optional
            自定义止损价格，配合 entry_price 使用时会覆盖 ATR止损
        entry_price : float, optional
            计划开仓价格，与 custom_stop_loss_price 配合使用

        Returns
        -------
        int
            建议仓位手数，已做上下界约束（min_lots ~ max_lots）
        """
        if account_balance <= 0:
            logger.error(f"[{self.symbol}] 账户净值异常: {account_balance}，返回最小仓位")
            return self.min_lots

        # 每笔最大可亏损金额
        max_risk_amount = account_balance * self.risk_per_trade

        # 合约乘数
        mult = self._get_multiplier()

        # 止损距离计算：优先使用自定义止损价，否则使用 ATR 倍数
        if custom_stop_loss_price is not None and entry_price is not None:
            # 模式A：已知止损价（精确止损模式）
            stop_distance = abs(entry_price - custom_stop_loss_price)
            if stop_distance <= 0:
                logger.warning(f"[{self.symbol}] 止损距离为0，返回最小仓位")
                return self.min_lots
            mode_label = f"止损价模式 | 进场={entry_price:.2f} 止损={custom_stop_loss_price:.2f}"
        else:
            # 模式B：ATR倍数止损（波动率自适应模式）
            atr = self._calc_atr()
            if atr is None or atr <= 0:
                logger.warning(f"[{self.symbol}] ATR 计算失败，返回最小仓位")
                return self.min_lots
            stop_distance = atr * stop_loss_atr_multiple
            mode_label = f"ATR模式 | ATR={atr:.4f} 倍数={stop_loss_atr_multiple}"

        # 计算原始手数（未取整）
        # 分母 = 止损距离（价格单位）× 合约乘数（数量/手）= 每手止损金额
        raw_lots = max_risk_amount / (stop_distance * mult)

        # 向下取整，保守管理风险（宁少勿多）
        lots = math.floor(raw_lots)

        # 边界约束
        lots = max(self.min_lots, min(self.max_lots, lots))

        logger.info(
            f"[{self.symbol}] 仓位计算 | {mode_label} | "
            f"净值={account_balance:,.0f} 风险金额={max_risk_amount:,.0f} "
            f"乘数={mult} 止损距离={stop_distance:.4f} "
            f"原始手数={raw_lots:.2f} → 建议手数={lots}手"
        )

        return lots

    def get_atr(self) -> Optional[float]:
        """
        直接获取当前 ATR 值（供外部策略查询）

        Returns
        -------
        float or None
            当前 ATR 值，数据不足时返回 None
        """
        return self._calc_atr()


# ══════════════════════════════════════════════════════════════════════════════
# 使用示例
# ══════════════════════════════════════════════════════════════════════════════

def example_main():
    """
    完整使用示例：将 AtrPositionSizer 集成到 TqSdk 趋势策略中

    策略逻辑（仅演示仓位管理，非完整交易策略）：
    - 订阅螺纹钢主力合约行情
    - 使用 AtrPositionSizer 在每次收到新 K 线时计算仓位
    - 当满足开仓条件（示例：价格突破20日高点）时，按 ATR 仓位下单
    """
    # ── 创建 TqSdk API 实例（使用模拟账户） ──────────────────────────────────
    # 实盘请替换为：
    #   api = TqApi(TqAccount("YOUR_BROKER", "ACCOUNT_ID", "PASSWORD"), auth=TqAuth("用户名","密码"))
    api = TqApi(TqSim(), auth=None)  # 示例用，实际需传入 TqAuth

    # ── 定义交易品种 ─────────────────────────────────────────────────────────
    SYMBOL = "SHFE.rb2501"     # 螺纹钢2501合约
    MULTIPLIER = 10.0           # 螺纹钢每手10吨
    RISK_PER_TRADE = 0.01       # 每笔风险1%账户净值
    ATR_PERIOD = 14             # 14根K线ATR

    # ── 实例化仓位管理器 ──────────────────────────────────────────────────────
    sizer = AtrPositionSizer(
        api=api,
        symbol=SYMBOL,
        atr_period=ATR_PERIOD,
        risk_per_trade=RISK_PER_TRADE,
        multiplier=MULTIPLIER,
        min_lots=1,
        max_lots=10,
        kline_duration_seconds=3600,  # 1小时K线
    )

    # ── 订阅账户信息（获取净值） ───────────────────────────────────────────────
    account = api.get_account()

    # ── 订阅行情（用于监测开仓信号） ─────────────────────────────────────────
    quote = api.get_quote(SYMBOL)

    # ── 记录上一次建议仓位（避免重复日志） ───────────────────────────────────
    last_recommended_lots = None

    print(f"{'='*60}")
    print(f"ATR动态仓位管理器 - 运行示例")
    print(f"合约: {SYMBOL} | 风险比例: {RISK_PER_TRADE:.1%} | ATR周期: {ATR_PERIOD}")
    print(f"{'='*60}")

    # ── 主循环 ────────────────────────────────────────────────────────────────
    # TqSdk 的事件驱动核心：wait_update() 会阻塞到有任何订阅数据更新
    # 每次 wait_update 返回后，检查哪些数据发生了变化
    while True:
        api.wait_update()

        # 检查 K 线是否有新数据（新K线形成或当前K线更新）
        if api.is_changing(sizer._klines):
            # 获取当前账户净值
            balance = account.balance
            if balance <= 0:
                continue  # 账户数据未就绪，跳过

            # ── 计算建议仓位（模式A：ATR倍数止损） ──────────────────────────
            lots_atr_mode = sizer.get_lots(
                account_balance=balance,
                stop_loss_atr_multiple=2.0,
            )

            # ── 计算建议仓位（模式B：自定义止损价） ─────────────────────────
            # 假设当前计划以最新价进场，止损设在最新价下方200点
            last_price = quote.last_price
            if last_price and last_price > 0:
                stop_price = last_price - 200  # 示例：固定200点止损
                lots_price_mode = sizer.get_lots(
                    account_balance=balance,
                    entry_price=last_price,
                    custom_stop_loss_price=stop_price,
                )
            else:
                lots_price_mode = None

            # 输出结果（仅在仓位建议变化时打印，减少刷屏）
            if lots_atr_mode != last_recommended_lots:
                last_recommended_lots = lots_atr_mode
                atr_val = sizer.get_atr()
                print(
                    f"\n[仓位更新] 账户净值={balance:,.0f}元 | "
                    f"ATR={atr_val:.2f if atr_val else 'N/A'} | "
                    f"ATR模式建议={lots_atr_mode}手"
                )
                if lots_price_mode is not None:
                    print(f"           价格止损模式建议={lots_price_mode}手 "
                          f"（进场={last_price:.0f} 止损={last_price-200:.0f}）")

            # ── 此处可添加实际开仓逻辑 ────────────────────────────────────────
            # 例如：
            # if 开仓信号成立:
            #     order = api.insert_order(
            #         symbol=SYMBOL,
            #         direction="BUY",
            #         offset="OPEN",
            #         volume=lots_atr_mode,  # 使用 ATR 计算的仓位
            #         limit_price=quote.ask_price1,
            #     )


if __name__ == "__main__":
    example_main()
