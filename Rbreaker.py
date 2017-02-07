# -*- coding:utf-8 -*-

from CloudQuant import MiniSimulator
import numpy as np
import pandas as pd

username = 'Harvey_Sun'
password = 'P948894dgmcsy'
Strategy_Name = 'Rbreaker'

INIT_CAP = 100000000
START_DATE = '20130101'
END_DATE = '20161231'
k1 = 0.35
k2 = 0.07
k3 = 0.25
div = 3
Fee_Rate = 0.001
program_path = 'C:/cStrategy/'


def initial(sdk):
    # 准备数据
    sdk.prepareData(['LZ_GPA_QUOTE_THIGH', 'LZ_GPA_QUOTE_TLOW', 'LZ_GPA_QUOTE_TCLOSE',
                     'LZ_GPA_INDEX_CSI500MEMBER', 'LZ_GPA_SLCIND_STOP_FLAG'])
    buy_and_hold = []
    buy_and_hold_time = []
    sdk.setGlobal('buy_and_hold', buy_and_hold)
    sdk.setGlobal('buy_and_hold_time', buy_and_hold_time)


def init_per_day(sdk):
    buy_and_hold = sdk.getGlobal('buy_and_hold')
    buy_and_hold_time = sdk.getGlobal('buy_and_hold_time')
    sdk.clearGlobal()
    sdk.setGlobal('buy_and_hold', buy_and_hold)
    sdk.setGlobal('buy_and_hold_time', buy_and_hold_time)

    today = sdk.getNowDate()
    sdk.sdklog(today, '========================================日期')
    # 获取当天中证500成分股
    in_zz500 = pd.Series(sdk.getFieldData('LZ_GPA_INDEX_CSI500MEMBER')[-1]) == 1
    stock_list = sdk.getStockList()
    zz500 = list(pd.Series(stock_list)[in_zz500])
    sdk.setGlobal('zz500', zz500)
    # 获取仓位信息
    positions = sdk.getPositions()
    sdk.sdklog(len(positions), '底仓股票数量')
    stock_position = dict([[i.code, 1] for i in positions])
    base_position = dict([i.code, i.optPosition] for i in positions)
    sdk.setGlobal('stock_position', stock_position)
    sdk.setGlobal('base_position', base_position)
    # 找到中证500外的有仓位的股票
    print len(set(stock_position.keys()))
    print len(set(zz500))
    set(stock_position.keys()) - set(zz500)
    out_zz500_stock = list(set(stock_position.keys()) - set(zz500))
    # 以下代码获取当天未停牌未退市的股票，即可交易股票
    not_stop = pd.isnull(sdk.getFieldData('LZ_GPA_SLCIND_STOP_FLAG')[-2:]).all(axis=0)  # 当日和前1日均没有停牌的股票
    zz500_available = list(pd.Series(stock_list)[np.logical_and(in_zz500, not_stop)])
    sdk.setGlobal('zz500_available', zz500_available)
    # 以下代码获取当天被移出中证500的有仓位的股票中可交易的股票
    out_zz500_available = list(set(pd.Series(stock_list)[not_stop]).intersection(set(out_zz500_stock)))
    sdk.setGlobal('out_zz500_available', out_zz500_available)
    print out_zz500_available
    # 订阅所有可交易的股票
    stock_available = list(set(zz500_available + out_zz500_available))
    sdk.sdklog(len(stock_available), '订阅股票数量')
    sdk.subscribeQuote(stock_available)
    # 找到所有可交易股票前1日四个价位
    high = pd.Series(sdk.getFieldData('LZ_GPA_QUOTE_THIGH')[-1], index=stock_list)[zz500_available]
    low = pd.Series(sdk.getFieldData('LZ_GPA_QUOTE_TLOW')[-1], index=stock_list)[zz500_available]
    close = pd.Series(sdk.getFieldData('LZ_GPA_QUOTE_TCLOSE')[-1], index=stock_list)[zz500_available]
    # 计算相关指标
    s_setup = high + k1 * (close - low)
    s_enter = (1 + k2) / 2 * (high + low) - k2 * low
    b_enter = (1 + k2) / 2 * (high + low) - k2 * high
    b_setup = low - k1 * (high - close)
    b_break = s_setup + k3 * (s_setup - b_setup)
    s_break = b_setup - k3 * (s_setup - b_setup)
    # 全局变量
    sdk.setGlobal('s_setup', s_setup)
    sdk.setGlobal('s_enter', s_enter)
    sdk.setGlobal('b_enter', b_enter)
    sdk.setGlobal('b_setup', b_setup)
    sdk.setGlobal('b_break', b_break)
    sdk.setGlobal('s_break', s_break)
    # 建立一个列表，来记录当天不能再交易的股票
    traded_stock = []
    sdk.setGlobal('traded_stock', traded_stock)


def strategy(sdk):
    if (sdk.getNowTime() >= '093000') & (sdk.getNowTime() <= '145500'):
        today = sdk.getNowDate()
        # 获取仓位信息及有仓位的股票
        positions = sdk.getPositions()
        position_dict = dict([[i.code, i.optPosition] for i in positions])
        # 找到目前有仓位且可交易的中证500外的股票
        out_zz500_available = sdk.getGlobal('out_zz500_available')
        # 获得中证500当日可交易的股票
        zz500_available = sdk.getGlobal('zz500_available')
        stock_available = list(set(zz500_available + out_zz500_available))
        quotes = sdk.getQuotes(stock_available)
        # 加载已交易股票
        traded_stock = sdk.getGlobal('traded_stock')
        # 获得当下还可交易的股票
        zz500_tradable = list(set(zz500_available) - set(traded_stock))
        # 有底仓的股票
        stock_position = sdk.getGlobal('stock_position')
        base_position = sdk.getGlobal('base_position')
        # 底仓开平记录
        buy_and_hold = sdk.getGlobal('buy_and_hold')
        buy_and_hold_time = sdk.getGlobal('buy_and_hold_time')

        # 开盘时获取最高价和最低价
        if sdk.getNowTime() == '093000':
            max_high = [quotes[stock].high for stock in zz500_available]
            min_low = [quotes[stock].low for stock in zz500_available]
            sdk.setGlobal('max_high', max_high)
            sdk.setGlobal('min_low', min_low)

            # 考虑被移出中证500的那些股票，卖出其底仓
            base_clear = []
            date_and_time = []
            for stock in out_zz500_available:
                position = position_dict[stock]
                price = quotes[stock].current
                order = [stock, price, position, -1]
                base_clear.append(order)
                date_and_time.append([today, sdk.getNowTime()])
                del stock_position[stock]
            sdk.makeOrders(base_clear)
            buy_and_hold += base_clear
            buy_and_hold_time += date_and_time
            sdk.sdklog(len(out_zz500_available), '清除底仓股票数量')

            # 计算可用资金
            number = sum(stock_position.values()) / 2  # 计算有多少个全仓股
            available_cash = (sdk.getAccountInfo().availableCash / (500 - number)) if number < 250 else 0

            # 对未建立底仓的股票建立底仓
            stock_to_build_base = list(set(zz500_available) - set(stock_position.keys()))
            if stock_to_build_base:
                base_hold = []
                date_and_time = []
                for stock in stock_to_build_base:
                    price = quotes[stock].current
                    volume = 100 * np.floor(available_cash * 0.5 / (100 * price))
                    if volume > 0:
                        order = [stock, price, volume, 1]
                        base_hold.append(order)
                        date_and_time.append([today, '093000'])
                        stock_position[stock] = 1
                        traded_stock.append(stock)
                sdk.makeOrders(base_hold)
                sdk.sdklog('%d/%d' % (len(traded_stock), len(stock_to_build_base)), '建立底仓股票数量')
                zz500_tradable = list(set(zz500_tradable) - set(stock_to_build_base))
                buy_and_hold += base_hold
                buy_and_hold_time += date_and_time

        if (sdk.getNowTime() >= '093000') & (sdk.getNowTime() < '145500'):
            # 获取当日最高价最低价
            max_high = sdk.getGlobal('max_high')
            min_low = sdk.getGlobal('min_low')
            high = [quotes[stock].high for stock in zz500_available]
            low = [quotes[stock].low for stock in zz500_available]
            max_high = pd.Series(np.where(high > max_high, high, max_high), index=zz500_available)
            min_low = pd.Series(np.where(low < min_low, low, min_low), index=zz500_available)
            sdk.setGlobal('max_high', max_high)
            sdk.setGlobal('min_low', min_low)

            # 计算条线
            s_setup = sdk.getGlobal('s_setup')
            s_enter = sdk.getGlobal('s_enter')
            b_enter = sdk.getGlobal('b_enter')
            b_setup = sdk.getGlobal('b_setup')
            b_break = sdk.getGlobal('b_break')
            s_break = sdk.getGlobal('s_break')
            up_line = s_enter + (max_high - s_setup) / div
            dn_line = b_enter - (b_setup - min_low) / div

            # 考虑当日中证500可交易的股票
            buy_orders = []
            sell_orders = []
            for stock in zz500_tradable:
                current_price = quotes[stock].current
                if (current_price > b_break[stock]) & (stock_position[stock] == 1):  # 突破Bbreak，做多
                    volume = base_position[stock]
                    order = [stock, current_price, volume, 1]
                    buy_orders.append(order)
                    stock_position[stock] = 2
                elif (current_price < s_break[stock]) & (stock_position[stock] == 1):  # 跌破Sbreak，做空
                    volume = base_position[stock]
                    order = [stock, current_price, volume, -1]
                    sell_orders.append(order)
                    stock_position[stock] = 0
                elif (current_price < up_line[stock]) & (b_break[stock] > max_high[stock] > s_setup[stock]) & (stock_position[stock] > 0):
                    volume = base_position[stock]
                    order = [stock, current_price, volume, -1]
                    sell_orders.append(order)
                    stock_position[stock] -= 1
                    if stock_position[stock] == 1:  # 平多后今日便不再交易
                        traded_stock.append(stock)
                elif (current_price > dn_line[stock]) & (s_break[stock] < min_low[stock] < b_setup[stock]) & (stock_position[stock] < 2):
                    volume = base_position[stock]
                    order = [stock, current_price, volume, 1]
                    buy_orders.append(order)
                    stock_position[stock] += 1
                    if stock_position[stock] == 1:  # 平空后近日便不再交易
                        traded_stock.append(stock)
                else:
                    pass
            sdk.makeOrders(sell_orders)
            sdk.makeOrders(buy_orders)
            # 记录下单数据
            if buy_orders or sell_orders:
                sdk.sdklog(sdk.getNowTime(), '=================时间')
                if buy_orders:
                    sdk.sdklog('Buy orders')
                    sdk.sdklog(np.array(buy_orders))
                if sell_orders:
                    sdk.sdklog('Sell orders')
                    sdk.sdklog(np.array(sell_orders))
        if sdk.getNowTime() == '145500':
            stock_to_clear = list(stock_position.keys())
            clear_orders = []
            for stock in stock_to_clear:
                if stock_position[stock] == 2:
                    price = quotes[stock].current
                    volume = base_position[stock]
                    order = [stock, price, volume, -1]
                    clear_orders.append(order)
                elif stock_position[stock] == 0:
                    price = quotes[stock].current
                    volume = base_position[stock]
                    order = [stock, price, volume, 1]
                    clear_orders.append(order)
                else:
                    pass

        sdk.setGlobal('traded_stock', traded_stock)
        sdk.setGlobal('stock_position', stock_position)
        sdk.setGlobal('buy_and_hold', buy_and_hold)
        sdk.setGlobal('buy_and_hold_time', buy_and_hold_time)

    if sdk.getNowTime == '150000':
        sdk.sdklog(sdk.getQueueOrders())

    if (sdk.getNowDate() == '20161230') & (sdk.getNowTime() == '150000'):
        buy_and_hold = sdk.getGlobal('buy_and_hold')
        buy_and_hold_time = sdk.getGlobal('buy_and_hold_time')
        temp = pd.DataFrame(buy_and_hold_time)
        temp = pd.concat([temp, pd.Series(buy_and_hold)], axis=1)
        pd.DataFrame(temp).to_csv('buy_and_hold.csv')


config = {
    'username': username,
    'password': password,
    'initCapital': INIT_CAP,
    'startDate': START_DATE,
    'endDate': END_DATE,
    'strategy': strategy,
    'initial': initial,
    'preparePerDay': init_per_day,
    'feeRate': Fee_Rate,
    'strategyName': Strategy_Name,
    'logfile': '%s.log' % Strategy_Name,
    'rootpath': program_path,
    'executeMode': 'M',
    'feeLimit': 5,
    'cycle': 1,
    'dealByVolume': True,
    'allowForTodayFactors': ['LZ_GPA_INDEX_CSI500MEMBER', 'LZ_GPA_SLCIND_STOP_FLAG']
}

if __name__ == "__main__":
    # 在线运行所需代码
    import os
    config['strategyID'] = os.path.splitext(os.path.split(__file__)[1])[0]
    MiniSimulator(**config).run()
