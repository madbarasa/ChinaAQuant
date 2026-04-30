"""
完整分析报告生成器 - 整合因子投资和事件研究

由于数据量巨大，本脚本采用抽样和优化的方法来加速分析
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

print("="*80)
print("金融量化分析 - 因子投资与事件研究")
print("版本: 1.1.0")
print("="*80)
print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# CONFIG & SETTINGS
# ============================================================================
CONFIG = {
    "VERSION": "1.1.0",
    "DATA_PATHS": {
        "PRICE_DATA_DIR": "price_data",
        "APPENDIX1": "Appendix1.db",
        "APPENDIX2": "Appendix2.db",
        "APPENDIX3": "Appendix3.db",
        "DIVIDEND_PROFIT": "CD_CompOfDivProfitInd.db",
        "LISTED_INFO": "STK_LISTEDCOINFOANL.db"
    },
    "FACTOR_PARAMS": {
        "PAST_PERF_PERIOD": 63,
        "MAX_WINDOW": 20,
        "VOL_WINDOW": 20,
        "N_QUINTILES": 5,
        "DATE_RANGE": ("2015-01-01", "2024-12-31")
    },
    "EVENT_STUDY_PARAMS": {
        "ESTIMATION_WINDOW": (-100, -11),
        "EVENT_WINDOW": (-10, 10),
        "MAX_SAMPLES": 500,
        "GOOD_EVENT_THRESHOLD": 60, # 行业分红比例 < 60%
        "BAD_EVENT_THRESHOLD": 80,  # 行业分红比例 > 80%
    },
    "BACKTEST_PARAMS": {
        "RF_RATE": 0.03,
        "WEIGHT_TYPES": ["equal", "value"]
    }
}

# ============================================================================
# 第一部分：因子投资分析
# ============================================================================

print("\n" + "="*80)
print("第一部分：因子投资分析")
print("="*80)

class QuickFactorAnalysis:
    def __init__(self):
        print("\n加载数据...")
        self.load_data()
    
    def load_data(self):
        """加载并预处理数据"""
        # 加载所有价格数据
        data_dir = Path(CONFIG["DATA_PATHS"]["PRICE_DATA_DIR"])
        price_dbs = list(data_dir.glob("TRD_Dalyr*.db"))
        
        dfs = []
        for db_path in price_dbs:
            with sqlite3.connect(db_path) as conn:
                table_name = db_path.stem
                # 只读取需要的列
                df = pd.read_sql(f"SELECT Stkcd, Trddt, Clsprc, Dsmvosd FROM {table_name}", conn)
                dfs.append(df)
        
        self.price_data = pd.concat(dfs, ignore_index=True)
        self.price_data['Trddt'] = pd.to_datetime(self.price_data['Trddt'])
        
        # 只保留配置范围的数据
        start_date, end_date = CONFIG["FACTOR_PARAMS"]["DATE_RANGE"]
        self.price_data = self.price_data[
            (self.price_data['Trddt'] >= start_date) & 
            (self.price_data['Trddt'] <= end_date)
        ]
        
        self.price_data = self.price_data.sort_values(['Stkcd', 'Trddt'])
        
        print(f"  数据量: {len(self.price_data):,} 条")
        print(f"  股票数: {self.price_data['Stkcd'].nunique()}")
        print(f"  日期范围: {self.price_data['Trddt'].min()} ~ {self.price_data['Trddt'].max()}")
    
    def calculate_factors_monthly(self):
        """计算月度因子"""
        print("\n计算因子...")
        
        # 计算收益率
        self.price_data['ret'] = self.price_data.groupby('Stkcd')['Clsprc'].pct_change()
        
        # 计算因子（使用向量化操作）
        print(f"  计算Past Performance ({CONFIG['FACTOR_PARAMS']['PAST_PERF_PERIOD']}日)...")
        self.price_data['PastPerf'] = self.price_data.groupby('Stkcd')['Clsprc'].transform(
            lambda x: x.pct_change(periods=CONFIG['FACTOR_PARAMS']['PAST_PERF_PERIOD'])
        )
        
        print(f"  计算MAX ({CONFIG['FACTOR_PARAMS']['MAX_WINDOW']}日)...")
        self.price_data['MAX'] = self.price_data.groupby('Stkcd')['ret'].transform(
            lambda x: x.rolling(window=CONFIG['FACTOR_PARAMS']['MAX_WINDOW'], min_periods=CONFIG['FACTOR_PARAMS']['MAX_WINDOW']).max()
        )
        
        print(f"  计算Volatility ({CONFIG['FACTOR_PARAMS']['VOL_WINDOW']}日)...")
        self.price_data['Volatility'] = self.price_data.groupby('Stkcd')['ret'].transform(
            lambda x: x.rolling(window=CONFIG['FACTOR_PARAMS']['VOL_WINDOW'], min_periods=CONFIG['FACTOR_PARAMS']['VOL_WINDOW']).std()
        )
        
        # 提取月末数据
        print("  提取月末数据...")
        self.price_data['YearMonth'] = self.price_data['Trddt'].dt.to_period('M')
        monthly = self.price_data.groupby(['Stkcd', 'YearMonth']).tail(1).copy()
        monthly['Date'] = monthly['Trddt']
        
        # 删除缺失值
        self.factors = monthly[['Stkcd', 'Date', 'PastPerf', 'MAX', 'Volatility', 'Clsprc', 'Dsmvosd']].dropna()
        
        print(f"  月度因子数据: {len(self.factors):,} 条")
        
        return self.factors
    
    def backtest_strategy(self, factor_name, weight_type='equal'):
        """回测因子策略"""
        print(f"\n回测 {factor_name} 因子 ({weight_type}权重)...")
        
        # 按因子值分组
        n_q = CONFIG["FACTOR_PARAMS"]["N_QUINTILES"]
        self.factors['quintile'] = self.factors.groupby('Date')[factor_name].transform(
            lambda x: pd.qcut(x, n_q, labels=False, duplicates='drop')
        )
        
        # 计算每组的下月收益
        returns_list = []
        dates = sorted(self.factors['Date'].unique())
        
        for i in range(len(dates) - 1):
            curr_date = dates[i]
            next_date = dates[i + 1]
            
            curr_data = self.factors[self.factors['Date'] == curr_date]
            next_data = self.factors[self.factors['Date'] == next_date]
            
            for q in range(5):
                stocks_in_q = curr_data[curr_data['quintile'] == q]['Stkcd'].values
                
                # 获取这些股票下月的数据
                next_stocks = next_data[next_data['Stkcd'].isin(stocks_in_q)]
                curr_stocks = curr_data[curr_data['quintile'] == q]
                
                # 合并
                merged = next_stocks[['Stkcd', 'Clsprc']].merge(
                    curr_stocks[['Stkcd', 'Clsprc', 'Dsmvosd']], 
                    on='Stkcd', 
                    suffixes=('_next', '_curr')
                )
                
                if len(merged) == 0:
                    continue
                
                merged['ret'] = (merged['Clsprc_next'] / merged['Clsprc_curr']) - 1
                
                # 计算组合收益
                if weight_type == 'equal':
                    port_ret = merged['ret'].mean()
                else:  # value-weighted
                    total_mv = merged['Dsmvosd'].sum()
                    if total_mv > 0:
                        merged['weight'] = merged['Dsmvosd'] / total_mv
                        port_ret = (merged['ret'] * merged['weight']).sum()
                    else:
                        port_ret = np.nan
                
                returns_list.append({
                    'Date': next_date,
                    'Quintile': q,
                    'Return': port_ret
                })
        
        returns_df = pd.DataFrame(returns_list)
        returns_pivot = returns_df.pivot(index='Date', columns='Quintile', values='Return')
        
        # 多空组合（做多最高组，做空最低组）
        n_q = CONFIG["FACTOR_PARAMS"]["N_QUINTILES"]
        if (n_q - 1) in returns_pivot.columns and 0 in returns_pivot.columns:
            returns_pivot['LongShort'] = returns_pivot[n_q - 1] - returns_pivot[0]
            returns_pivot['Long'] = returns_pivot[n_q - 1]
            returns_pivot['Short'] = returns_pivot[0]
        
        return returns_pivot
    
    def calculate_metrics(self, returns):
        """计算绩效指标"""
        returns = returns.dropna()
        if len(returns) == 0:
            return {}
        
        rf = CONFIG["BACKTEST_PARAMS"]["RF_RATE"]
        annual_ret = (1 + returns.mean()) ** 12 - 1
        annual_vol = returns.std() * np.sqrt(12)
        sharpe = (returns.mean() - rf/12) / returns.std() * np.sqrt(12) if returns.std() > 0 else 0
        cum_ret = (1 + returns).cumprod().iloc[-1] - 1
        
        return {
            'Annual_Return': annual_ret,
            'Annual_Volatility': annual_vol,
            'Sharpe_Ratio': sharpe,
            'Cumulative_Return': cum_ret
        }
    
    def run_analysis(self):
        """运行完整分析"""
        self.calculate_factors_monthly()
        
        results = {}
        
        # 分析三个因子
        for factor in ['PastPerf', 'MAX', 'Volatility']:
            print(f"\n{'='*60}")
            print(f"分析因子: {factor}")
            print(f"{'='*60}")
            
            # 等权重
            returns_ew = self.backtest_strategy(factor, 'equal')
            
            perf_ls = self.calculate_metrics(returns_ew['LongShort'])
            perf_long = self.calculate_metrics(returns_ew['Long'])
            perf_short = self.calculate_metrics(returns_ew['Short'])
            
            print(f"\n【{factor} - 等权重】")
            print(f"多空组合年化收益: {perf_ls['Annual_Return']:.2%}")
            print(f"年化波动率: {perf_ls['Annual_Volatility']:.2%}")
            print(f"夏普比率: {perf_ls['Sharpe_Ratio']:.4f}")
            print(f"\n多头年化收益: {perf_long['Annual_Return']:.2%}")
            print(f"空头年化收益: {perf_short['Annual_Return']:.2%}")
            print(f"主要贡献: {'多头' if abs(perf_long['Annual_Return']) > abs(perf_short['Annual_Return']) else '空头'}")
            
            results[factor] = {
                'returns_ew': returns_ew,
                'perf_ls': perf_ls,
                'perf_long': perf_long,
                'perf_short': perf_short
            }
        
        # MAX因子的市值权重
        print(f"\n{'='*60}")
        print("MAX因子 - 市值权重")
        print(f"{'='*60}")
        
        returns_vw = self.backtest_strategy('MAX', 'value')
        perf_ls_vw = self.calculate_metrics(returns_vw['LongShort'])
        
        print(f"\n【MAX - 市值权重】")
        print(f"多空组合年化收益: {perf_ls_vw['Annual_Return']:.2%}")
        print(f"年化波动率: {perf_ls_vw['Annual_Volatility']:.2%}")
        print(f"夏普比率: {perf_ls_vw['Sharpe_Ratio']:.4f}")
        
        print(f"\n等权重 vs 市值权重:")
        print(f"  等权重: {results['MAX']['perf_ls']['Annual_Return']:.2%}")
        print(f"  市值权重: {perf_ls_vw['Annual_Return']:.2%}")
        print(f"  更优: {'市值权重' if perf_ls_vw['Annual_Return'] > results['MAX']['perf_ls']['Annual_Return'] else '等权重'}")
        
        results['MAX_VW'] = {
            'returns_vw': returns_vw,
            'perf_ls_vw': perf_ls_vw
        }
        
        self.results = results
        return results
    
    def plot_results(self):
        """绘制结果"""
        print("\n绘制累计收益率图表...")
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        factors = ['PastPerf', 'MAX', 'Volatility']
        titles = ['Past Performance因子', 'MAX因子', 'Volatility因子']
        
        for idx, (factor, title) in enumerate(zip(factors, titles)):
            ax = axes[idx]
            
            returns = self.results[factor]['returns_ew']['LongShort'].dropna()
            cum_ret = (1 + returns).cumprod()
            
            ax.plot(cum_ret.index, cum_ret.values, label=f'{factor}多空组合', linewidth=2, color='blue')
            ax.axhline(y=1, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
            
            ax.set_title(f'{title} - 累计收益率', fontsize=14, fontweight='bold')
            ax.set_xlabel('日期', fontsize=12)
            ax.set_ylabel('累计收益 (初始=1)', fontsize=12)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            
            final_ret = (cum_ret.iloc[-1] - 1) * 100
            ax.text(0.02, 0.95, f'累计收益: {final_ret:.2f}%', 
                   transform=ax.transAxes, fontsize=11, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.7))
        
        plt.tight_layout()
        plt.savefig('factor_analysis_results.png', dpi=300, bbox_inches='tight')
        print("图表已保存: factor_analysis_results.png")

# 运行因子分析
fa = QuickFactorAnalysis()
results_factor = fa.run_analysis()
fa.plot_results()

print("\n" + "="*80)
print("第一部分完成！")
print("="*80)

# ============================================================================
# 第二部分：事件研究
# ============================================================================

print("\n" + "="*80)
print("第二部分：事件研究")
print("="*80)

class QuickEventStudy:
    def __init__(self, price_data):
        print("\n使用已加载的价格数据...")
        self.price_data = price_data
        self.load_event_data()
    
    def load_event_data(self):
        """加载事件相关数据"""
        print("\n加载事件数据...")
        
        # 分红预案
        with sqlite3.connect(CONFIG["DATA_PATHS"]["APPENDIX3"]) as conn:
            self.dividend = pd.read_sql("SELECT * FROM Appendix3", conn)
        self.dividend['Ppdadt'] = pd.to_datetime(self.dividend['Ppdadt'])
        self.dividend = self.dividend[(self.dividend['Finyear'] >= 2015) & (self.dividend['Finyear'] <= 2024)]
        
        # 行业分红比例
        with sqlite3.connect(CONFIG["DATA_PATHS"]["DIVIDEND_PROFIT"]) as conn:
            self.ind_div = pd.read_sql("SELECT * FROM CD_CompOfDivProfitInd", conn)
        self.ind_div = self.ind_div[(self.ind_div['DivdendYear'] >= 2015) & (self.ind_div['DivdendYear'] <= 2024)]
        
        # 行业代码
        with sqlite3.connect(CONFIG["DATA_PATHS"]["LISTED_INFO"]) as conn:
            ind_code = pd.read_sql("SELECT * FROM STK_LISTEDCOINFOANL", conn)
        ind_code['EndDate'] = pd.to_datetime(ind_code['EndDate'])
        self.ind_code = ind_code.sort_values('EndDate').groupby('Symbol').tail(1)
        
        print(f"  分红事件: {len(self.dividend):,}")
        print(f"  行业分红数据: {len(self.ind_div):,}")
        print(f"  公司行业映射: {len(self.ind_code):,}")
    
    def classify_events(self):
        """分类事件"""
        print("\n分类事件...")
        
        # 合并数据
        events = self.dividend.merge(
            self.ind_code[['Symbol', 'IndustryCode']], 
            left_on='Stkcd', right_on='Symbol', how='left'
        )
        
        events = events.merge(
            self.ind_div[['DivdendYear', 'IndustryCode', 'DivdendToProfitableRate']], 
            left_on=['Finyear', 'IndustryCode'], 
            right_on=['DivdendYear', 'IndustryCode'], 
            how='left'
        )
        
        # 判断分红类型
        events['is_dividend'] = events['Ppcont'].str.contains('派|分红|现金', na=False)
        events['is_no_div'] = events['Ppcont'].str.contains('不分配不转增|不派|不分配', na=False)
        
        # 利好事件: 行业分红比例 < threshold, 公司分红
        good_threshold = CONFIG["EVENT_STUDY_PARAMS"]["GOOD_EVENT_THRESHOLD"]
        self.good_events = events[
            (events['DivdendToProfitableRate'] < good_threshold) & 
            (events['is_dividend'] == True)
        ].copy()
        
        # 利空事件: 行业分红比例 > threshold, 公司不分红
        bad_threshold = CONFIG["EVENT_STUDY_PARAMS"]["BAD_EVENT_THRESHOLD"]
        self.bad_events = events[
            (events['DivdendToProfitableRate'] > bad_threshold) & 
            (events['is_no_div'] == True)
        ].copy()
        
        print(f"  利好事件: {len(self.good_events):,}")
        print(f"  利空事件: {len(self.bad_events):,}")
        
        return self.good_events, self.bad_events
    
    def calculate_ar(self, events, event_type='good'):
        """计算异常收益（简化版本，采样加速）"""
        print(f"\n计算{event_type}事件的异常收益...")
        
        # 为加速，随机采样
        max_samples = CONFIG["EVENT_STUDY_PARAMS"]["MAX_SAMPLES"]
        if len(events) > max_samples:
            events = events.sample(n=max_samples, random_state=42)
            print(f"  采样{len(events)}个事件进行分析")
        
        ar_list = []
        
        for idx, event in events.iterrows():
            stkcd = event['Stkcd']
            event_date = event['Ppdadt']
            
            stock_data = self.price_data[self.price_data['Stkcd'] == stkcd].copy()
            if len(stock_data) == 0:
                continue
            
            stock_data = stock_data.sort_values('Trddt')
            stock_data['days_diff'] = (stock_data['Trddt'] - event_date).dt.days
            
            # 估计窗口与事件窗口
            est_win = CONFIG["EVENT_STUDY_PARAMS"]["ESTIMATION_WINDOW"]
            event_win = CONFIG["EVENT_STUDY_PARAMS"]["EVENT_WINDOW"]
            
            # 估计窗口
            est_data = stock_data[(stock_data['days_diff'] >= est_win[0]) & (stock_data['days_diff'] <= est_win[1])]
            if len(est_data) < 30:
                continue
            
            exp_ret = est_data['ret'].mean()
            
            # 事件窗口
            event_data = stock_data[(stock_data['days_diff'] >= event_win[0]) & (stock_data['days_diff'] <= event_win[1])]
            
            for _, row in event_data.iterrows():
                ar_list.append({
                    'Stkcd': stkcd,
                    'Day': row['days_diff'],
                    'AR': row['ret'] - exp_ret
                })
        
        ar_df = pd.DataFrame(ar_list)
        print(f"  计算完成: {len(ar_df):,} 个观测值")
        
        return ar_df
    
    def calculate_aar_caar(self, ar_df):
        """计算AAR和CAAR"""
        aar = ar_df.groupby('Day')['AR'].agg([
            ('AAR', 'mean'),
            ('StdErr', lambda x: x.std() / np.sqrt(len(x))),
            ('N', 'count')
        ]).sort_index()
        
        event_win = CONFIG["EVENT_STUDY_PARAMS"]["EVENT_WINDOW"]
        aar = aar[(aar.index >= event_win[0]) & (aar.index <= event_win[1])]
        aar['t_stat'] = aar['AAR'] / aar['StdErr']
        aar['p_value'] = 2 * (1 - stats.t.cdf(np.abs(aar['t_stat']), aar['N'] - 1))
        aar['CAAR'] = aar['AAR'].cumsum()
        
        return aar
    
    def run_event_study(self):
        """运行事件研究"""
        self.classify_events()
        
        # 计算异常收益
        ar_good = self.calculate_ar(self.good_events, '利好')
        ar_bad = self.calculate_ar(self.bad_events, '利空')
        
        # 计算AAR和CAAR
        aar_good = self.calculate_aar_caar(ar_good)
        aar_bad = self.calculate_aar_caar(ar_bad)
        
        print("\n【利好事件 - 关键日期】")
        for day in [0, 7, 10]:
            if day in aar_good.index:
                row = aar_good.loc[day]
                sig = '***' if row['p_value'] < 0.01 else ('**' if row['p_value'] < 0.05 else '*' if row['p_value'] < 0.1 else '')
                print(f"  T+{day}: AAR={row['AAR']:.4%}, CAAR={row['CAAR']:.4%}, t={row['t_stat']:.2f} {sig}")
        
        print("\n【利空事件 - 关键日期】")
        for day in [0, 7, 10]:
            if day in aar_bad.index:
                row = aar_bad.loc[day]
                sig = '***' if row['p_value'] < 0.01 else ('**' if row['p_value'] < 0.05 else '*' if row['p_value'] < 0.1 else '')
                print(f"  T+{day}: AAR={row['AAR']:.4%}, CAAR={row['CAAR']:.4%}, t={row['t_stat']:.2f} {sig}")
        
        self.aar_good = aar_good
        self.aar_bad = aar_bad
        
        return aar_good, aar_bad
    
    def plot_results(self):
        """绘制结果"""
        print("\n绘制事件研究图表...")
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 利好事件
        ax1 = axes[0, 0]
        ax1.bar(self.aar_good.index, self.aar_good['AAR'], alpha=0.7, color='green')
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='事件日')
        ax1.set_title('利好事件 - AAR', fontsize=14, fontweight='bold')
        ax1.set_xlabel('事件日相对天数')
        ax1.set_ylabel('平均异常收益率')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        ax2 = axes[0, 1]
        ax2.plot(self.aar_good.index, self.aar_good['CAAR'], linewidth=2.5, color='darkgreen', marker='o')
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax2.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='事件日')
        ax2.fill_between(self.aar_good.index, 0, self.aar_good['CAAR'], alpha=0.3, color='green')
        ax2.set_title('利好事件 - CAAR', fontsize=14, fontweight='bold')
        ax2.set_xlabel('事件日相对天数')
        ax2.set_ylabel('累积平均异常收益率')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 利空事件
        ax3 = axes[1, 0]
        ax3.bar(self.aar_bad.index, self.aar_bad['AAR'], alpha=0.7, color='red')
        ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax3.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='事件日')
        ax3.set_title('利空事件 - AAR', fontsize=14, fontweight='bold')
        ax3.set_xlabel('事件日相对天数')
        ax3.set_ylabel('平均异常收益率')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        ax4 = axes[1, 1]
        ax4.plot(self.aar_bad.index, self.aar_bad['CAAR'], linewidth=2.5, color='darkred', marker='o')
        ax4.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax4.axvline(x=0, color='red', linestyle='--', linewidth=1.5, label='事件日')
        ax4.fill_between(self.aar_bad.index, 0, self.aar_bad['CAAR'], alpha=0.3, color='red')
        ax4.set_title('利空事件 - CAAR', fontsize=14, fontweight='bold')
        ax4.set_xlabel('事件日相对天数')
        ax4.set_ylabel('累积平均异常收益率')
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('event_study_results.png', dpi=300, bbox_inches='tight')
        print("图表已保存: event_study_results.png")

# 运行事件研究
es = QuickEventStudy(fa.price_data)
aar_good, aar_bad = es.run_event_study()
es.plot_results()

print("\n" + "="*80)
print("第二部分完成！")
print("="*80)

# ============================================================================
# 生成总结报告
# ============================================================================

print("\n" + "="*80)
print("分析总结")
print("="*80)

print("\n【因子投资分析总结】")
print("\n1. 三个因子的多空组合绩效:")
for factor in ['PastPerf', 'MAX', 'Volatility']:
    perf = fa.results[factor]['perf_ls']
    print(f"\n   {factor}:")
    print(f"     年化收益: {perf['Annual_Return']:.2%}")
    print(f"     年化波动: {perf['Annual_Volatility']:.2%}")
    print(f"     夏普比率: {perf['Sharpe_Ratio']:.4f}")

print("\n2. MAX因子：等权重 vs 市值权重")
print(f"   等权重年化收益: {fa.results['MAX']['perf_ls']['Annual_Return']:.2%}")
print(f"   市值权重年化收益: {fa.results['MAX_VW']['perf_ls_vw']['Annual_Return']:.2%}")

print("\n【事件研究总结】")
print(f"\n1. 利好事件（低行业分红率下公司分红）:")
print(f"   事件日(T+0) AAR: {aar_good.loc[0, 'AAR']:.4%}" if 0 in aar_good.index else "")
print(f"   T+10日 CAAR: {aar_good.loc[10, 'CAAR']:.4%}" if 10 in aar_good.index else "")

print(f"\n2. 利空事件（高行业分红率下公司不分红）:")
print(f"   事件日(T+0) AAR: {aar_bad.loc[0, 'AAR']:.4%}" if 0 in aar_bad.index else "")
print(f"   T+10日 CAAR: {aar_bad.loc[10, 'CAAR']:.4%}" if 10 in aar_bad.index else "")

print("\n【投资策略建议】")
print("\n基于因子投资:")
print("- Past Performance因子显示动量效应")
print("- MAX因子捕捉极端收益特征")
print("- Volatility因子反映风险特征")
print("- 建议：构建多因子组合，分散单因子风险")

print("\n基于事件研究:")
print("- 监控行业分红比例异常的公司")
print("- 在公告日前后进行事件驱动交易")
print("- 结合基本面分析，提高成功率")

print("\n" + "="*80)
print(f"分析完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("所有图表已保存！")
print("="*80)

