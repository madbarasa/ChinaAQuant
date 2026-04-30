"""
因子投资分析和事件研究 - 完整实现

数据说明:
- TRD_Dalyr*.db: 日度交易数据 (Stkcd股票代码, Trddt交易日期, Clsprc收盘价, Dsmvosd流通市值)
- Appendix1.db: 沪深300成分股
- Appendix2.db: 中证500成分股
- Appendix3.db: 分红预案数据 (Stkcd, Finyear, Ppdadt预案公告日期, Ppcont预案内容)
- CD_CompOfDivProfitInd.db: 分行业现金分红比例
- STK_LISTEDCOINFOANL.db: 上市公司行业代码
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

class FactorAnalysis:
    def __init__(self):
        self.price_data = None
        self.load_all_price_data()
        
    def load_all_price_data(self):
        """加载所有价格数据并合并"""
        print("正在加载价格数据...")
        
        price_dbs = [
            'price_data/TRD_Dalyr.db',
            'price_data/TRD_Dalyr1.db',
            'price_data/TRD_Dalyr2.db',
            'price_data/TRD_Dalyr3.db',
            'price_data/TRD_Dalyr4.db',
            'price_data/TRD_Dalyr5.db',
            'price_data/TRD_Dalyr6.db',
            'price_data/TRD_Dalyr7.db',
            'price_data/TRD_Dalyr8.db',
            'price_data/TRD_Dalyr9.db'
        ]
        
        dfs = []
        for db_path in price_dbs:
            if Path(db_path).exists():
                conn = sqlite3.connect(db_path)
                table_name = Path(db_path).stem
                df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
                dfs.append(df)
                conn.close()
                print(f"  加载 {db_path}: {len(df):,} 条记录")
        
        # 合并所有数据
        self.price_data = pd.concat(dfs, ignore_index=True)
        self.price_data['Trddt'] = pd.to_datetime(self.price_data['Trddt'])
        self.price_data = self.price_data.sort_values(['Stkcd', 'Trddt'])
        
        print(f"\n总共加载 {len(self.price_data):,} 条价格记录")
        print(f"日期范围: {self.price_data['Trddt'].min()} 到 {self.price_data['Trddt'].max()}")
        print(f"股票数量: {self.price_data['Stkcd'].nunique()}")
        
    def calculate_returns(self):
        """计算日收益率"""
        print("\n计算日收益率...")
        self.price_data['ret'] = self.price_data.groupby('Stkcd')['Clsprc'].pct_change()
        
    def calculate_factors(self, start_date='2015-01-01', end_date='2024-12-31'):
        """
        计算三个因子:
        1. Past Performance: 过去3个月的持有期收益率
        2. MAX: 过去20个交易日的最高日收益率
        3. Volatility: 过去20个交易日的日收益率标准差
        """
        print("\n计算因子指标...")
        
        # 筛选日期范围
        self.price_data = self.price_data[
            (self.price_data['Trddt'] >= start_date) & 
            (self.price_data['Trddt'] <= end_date)
        ]
        
        # 计算收益率
        self.calculate_returns()
        
        print("计算滚动因子...")
        
        # 按股票分组，使用向量化操作
        self.price_data['PastPerf'] = self.price_data.groupby('Stkcd')['Clsprc'].transform(
            lambda x: x.pct_change(periods=63)
        )
        
        self.price_data['MAX'] = self.price_data.groupby('Stkcd')['ret'].transform(
            lambda x: x.rolling(window=20, min_periods=20).max()
        )
        
        self.price_data['Volatility'] = self.price_data.groupby('Stkcd')['ret'].transform(
            lambda x: x.rolling(window=20, min_periods=20).std()
        )
        
        # 获取每月最后一个交易日的数据
        print("提取月末数据...")
        self.price_data['YearMonth'] = self.price_data['Trddt'].dt.to_period('M')
        
        # 取每月最后一天
        monthly_data = self.price_data.sort_values('Trddt').groupby(['Stkcd', 'YearMonth']).tail(1)
        
        # 选择需要的列
        self.factors = monthly_data[['Stkcd', 'Trddt', 'PastPerf', 'MAX', 'Volatility', 'Clsprc', 'Dsmvosd']].copy()
        self.factors.rename(columns={'Trddt': 'Date'}, inplace=True)
        
        # 删除缺失值
        self.factors = self.factors.dropna()
        
        print(f"\n因子数据生成完成: {len(self.factors):,} 条记录")
        print(f"日期范围: {self.factors['Date'].min()} 到 {self.factors['Date'].max()}")
        print(f"股票数量: {self.factors['Stkcd'].nunique()}")
        
        return self.factors
    
    def form_portfolios(self, factor_name, n_groups=5, weight_type='equal'):
        """
        构建多空组合
        
        Parameters:
        - factor_name: 因子名称 ('PastPerf', 'MAX', 'Volatility')
        - n_groups: 分组数量，默认5组
        - weight_type: 权重类型 ('equal'等权重, 'value'市值权重)
        """
        print(f"\n构建{factor_name}因子的多空组合 (权重类型: {weight_type})...")
        
        # 每月分组
        self.factors['quintile'] = self.factors.groupby('Date')[factor_name].transform(
            lambda x: pd.qcut(x, n_groups, labels=False, duplicates='drop')
        )
        
        # 计算下月收益率
        self.factors['next_month'] = self.factors.groupby('Stkcd')['Date'].shift(-1)
        
        portfolio_returns = []
        
        for date in self.factors['Date'].unique():
            month_data = self.factors[self.factors['Date'] == date]
            
            # 获取下月数据
            next_month = date + pd.DateOffset(months=1)
            next_month_data = self.factors[self.factors['Date'] == next_month]
            
            if len(next_month_data) == 0:
                continue
            
            for group in range(n_groups):
                group_stocks = month_data[month_data['quintile'] == group]['Stkcd'].values
                
                # 下月这些股票的表现
                group_next = next_month_data[next_month_data['Stkcd'].isin(group_stocks)]
                
                if len(group_next) == 0:
                    continue
                
                # 当月的市值
                group_curr = month_data[month_data['quintile'] == group]
                
                # 计算收益率
                merged = group_next[['Stkcd', 'Clsprc']].merge(
                    group_curr[['Stkcd', 'Clsprc', 'Dsmvosd']], 
                    on='Stkcd', 
                    suffixes=('_next', '_curr')
                )
                
                merged['ret'] = (merged['Clsprc_next'] / merged['Clsprc_curr']) - 1
                
                # 计算组合收益率
                if weight_type == 'equal':
                    portfolio_ret = merged['ret'].mean()
                elif weight_type == 'value':
                    total_mv = merged['Dsmvosd'].sum()
                    if total_mv > 0:
                        merged['weight'] = merged['Dsmvosd'] / total_mv
                        portfolio_ret = (merged['ret'] * merged['weight']).sum()
                    else:
                        portfolio_ret = np.nan
                else:
                    portfolio_ret = np.nan
                
                portfolio_returns.append({
                    'Date': next_month,
                    'Group': group,
                    'Return': portfolio_ret,
                    'N_stocks': len(merged)
                })
        
        portfolio_df = pd.DataFrame(portfolio_returns)
        
        # 计算多空组合收益 (做多最高组，做空最低组)
        long_short = portfolio_df.pivot(index='Date', columns='Group', values='Return')
        
        if n_groups - 1 in long_short.columns and 0 in long_short.columns:
            long_short['LongShort'] = long_short[n_groups - 1] - long_short[0]
            long_short['Long'] = long_short[n_groups - 1]
            long_short['Short'] = long_short[0]
        
        return long_short
    
    def calculate_performance(self, returns_series, name="Portfolio"):
        """计算投资组合绩效指标"""
        returns = returns_series.dropna()
        
        if len(returns) == 0:
            return {}
        
        # 年化收益率 (月度收益转年化)
        annual_return = (1 + returns.mean()) ** 12 - 1
        
        # 年化波动率
        annual_vol = returns.std() * np.sqrt(12)
        
        # 夏普比率 (假设无风险利率为3%)
        rf = 0.03 / 12  # 月度无风险利率
        sharpe = (returns.mean() - rf) / returns.std() * np.sqrt(12) if returns.std() > 0 else 0
        
        # 累计收益率
        cumulative_return = (1 + returns).cumprod().iloc[-1] - 1
        
        return {
            'Name': name,
            'Annual_Return': annual_return,
            'Annual_Volatility': annual_vol,
            'Sharpe_Ratio': sharpe,
            'Cumulative_Return': cumulative_return,
            'N_Months': len(returns)
        }
    
    def run_factor_analysis(self):
        """运行完整的因子分析"""
        print("\n" + "="*80)
        print("开始因子投资分析")
        print("="*80)
        
        # 计算因子
        self.calculate_factors()
        
        results = {}
        
        # 对三个因子分别分析
        for factor in ['PastPerf', 'MAX', 'Volatility']:
            print(f"\n{'='*80}")
            print(f"分析因子: {factor}")
            print(f"{'='*80}")
            
            # (1) 等权重多空组合
            ls_returns = self.form_portfolios(factor, n_groups=5, weight_type='equal')
            
            # 计算绩效
            perf_ls = self.calculate_performance(ls_returns['LongShort'], f"{factor}_LongShort")
            perf_long = self.calculate_performance(ls_returns['Long'], f"{factor}_Long")
            perf_short = self.calculate_performance(ls_returns['Short'], f"{factor}_Short")
            
            results[factor] = {
                'returns': ls_returns,
                'performance': {
                    'LongShort': perf_ls,
                    'Long': perf_long,
                    'Short': perf_short
                }
            }
            
            # 打印结果
            print(f"\n【{factor}因子 - 等权重多空组合绩效】")
            print(f"多空组合:")
            print(f"  年化收益率: {perf_ls['Annual_Return']:.2%}")
            print(f"  年化波动率: {perf_ls['Annual_Volatility']:.2%}")
            print(f"  夏普比率: {perf_ls['Sharpe_Ratio']:.4f}")
            
            print(f"\n多头组合:")
            print(f"  年化收益率: {perf_long['Annual_Return']:.2%}")
            
            print(f"\n空头组合:")
            print(f"  年化收益率: {perf_short['Annual_Return']:.2%}")
            
            # 分析多头和空头的贡献
            long_contrib = perf_long['Annual_Return']
            short_contrib = -perf_short['Annual_Return']  # 做空收益是负的股价收益
            
            print(f"\n多空收益分解:")
            print(f"  多头贡献: {long_contrib:.2%}")
            print(f"  空头贡献: {short_contrib:.2%}")
            print(f"  主要贡献方: {'多头' if abs(long_contrib) > abs(short_contrib) else '空头'}")
        
        # (3) MAX因子的市值权重组合
        print(f"\n{'='*80}")
        print(f"MAX因子 - 流通市值权重组合")
        print(f"{'='*80}")
        
        ls_returns_vw = self.form_portfolios('MAX', n_groups=5, weight_type='value')
        perf_ls_vw = self.calculate_performance(ls_returns_vw['LongShort'], "MAX_LongShort_VW")
        
        print(f"\n【MAX因子 - 市值权重多空组合绩效】")
        print(f"  年化收益率: {perf_ls_vw['Annual_Return']:.2%}")
        print(f"  年化波动率: {perf_ls_vw['Annual_Volatility']:.2%}")
        print(f"  夏普比率: {perf_ls_vw['Sharpe_Ratio']:.4f}")
        
        print(f"\n【与等权重对比】")
        perf_ls_ew = results['MAX']['performance']['LongShort']
        print(f"  等权重年化收益: {perf_ls_ew['Annual_Return']:.2%}")
        print(f"  市值权重年化收益: {perf_ls_vw['Annual_Return']:.2%}")
        print(f"  更优策略: {'市值权重' if perf_ls_vw['Annual_Return'] > perf_ls_ew['Annual_Return'] else '等权重'}")
        
        results['MAX_VW'] = {
            'returns': ls_returns_vw,
            'performance': {'LongShort': perf_ls_vw}
        }
        
        self.results = results
        return results
    
    def plot_cumulative_returns(self):
        """绘制累计收益率曲线并与基准对比"""
        print(f"\n{'='*80}")
        print("绘制累计收益率曲线")
        print(f"{'='*80}")
        
        # 加载基准指数数据
        benchmark = self.calculate_benchmark()
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        
        factors = ['PastPerf', 'MAX', 'Volatility']
        titles = ['Past Performance因子', 'MAX因子', 'Volatility因子']
        
        for idx, (factor, title) in enumerate(zip(factors, titles)):
            ax = axes[idx]
            
            # 策略累计收益
            returns = self.results[factor]['returns']['LongShort'].dropna()
            cum_ret = (1 + returns).cumprod()
            
            # 对齐基准数据
            aligned_benchmark = benchmark.reindex(cum_ret.index, method='ffill')
            
            # 绘图
            ax.plot(cum_ret.index, cum_ret.values, label=f'{factor}多空组合', linewidth=2)
            ax.plot(cum_ret.index, aligned_benchmark.values, label='基准指数(50%沪深300+50%中证500)', 
                   linewidth=2, linestyle='--', alpha=0.7)
            
            ax.set_title(f'{title} - 累计收益率', fontsize=14, fontweight='bold')
            ax.set_xlabel('日期', fontsize=12)
            ax.set_ylabel('累计收益率', fontsize=12)
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # 添加性能标注
            final_return = (cum_ret.iloc[-1] - 1) * 100
            benchmark_return = (aligned_benchmark.iloc[-1] - 1) * 100
            ax.text(0.02, 0.95, f'策略收益: {final_return:.2f}%\n基准收益: {benchmark_return:.2f}%', 
                   transform=ax.transAxes, fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig('factor_cumulative_returns.png', dpi=300, bbox_inches='tight')
        print("累计收益率图表已保存: factor_cumulative_returns.png")
        
        return fig
    
    def calculate_benchmark(self):
        """计算基准指数 (50%沪深300 + 50%中证500)"""
        print("\n计算基准指数收益率...")
        
        # 加载指数成分股
        conn1 = sqlite3.connect('Appendix1.db')
        hs300 = pd.read_sql("SELECT * FROM Appendix1", conn1)
        conn1.close()
        
        conn2 = sqlite3.connect('Appendix2.db')
        zz500 = pd.read_sql("SELECT * FROM Appendix2", conn2)
        conn2.close()
        
        # 转换日期格式
        hs300['Date'] = pd.to_datetime(hs300['纳入Date'], format='%Y%m%d')
        zz500['Date'] = pd.to_datetime(zz500['纳入Date'], format='%Y%m%d')
        
        # 简化版本：使用月度重采样
        monthly_dates = self.factors['Date'].unique()
        
        benchmark_returns = []
        
        for i in range(1, len(monthly_dates)):
            curr_date = monthly_dates[i-1]
            next_date = monthly_dates[i]
            
            # 沪深300收益
            hs300_stocks = hs300[hs300['Date'] <= curr_date]['成分券代码Constituent Code'].unique()
            hs300_ret = self._calculate_index_return(hs300_stocks, curr_date, next_date)
            
            # 中证500收益
            zz500_stocks = zz500[zz500['Date'] <= curr_date]['成分券代码Constituent Code'].unique()
            zz500_ret = self._calculate_index_return(zz500_stocks, curr_date, next_date)
            
            # 50-50组合
            if not np.isnan(hs300_ret) and not np.isnan(zz500_ret):
                benchmark_ret = 0.5 * hs300_ret + 0.5 * zz500_ret
                benchmark_returns.append({'Date': next_date, 'Return': benchmark_ret})
        
        benchmark_df = pd.DataFrame(benchmark_returns)
        benchmark_df = benchmark_df.set_index('Date')['Return']
        
        return (1 + benchmark_df).cumprod()
    
    def _calculate_index_return(self, stock_list, curr_date, next_date):
        """计算指数收益率"""
        if len(stock_list) == 0:
            return np.nan
        
        curr_prices = self.factors[
            (self.factors['Stkcd'].isin(stock_list)) & 
            (self.factors['Date'] == curr_date)
        ][['Stkcd', 'Clsprc']]
        
        next_prices = self.factors[
            (self.factors['Stkcd'].isin(stock_list)) & 
            (self.factors['Date'] == next_date)
        ][['Stkcd', 'Clsprc']]
        
        merged = curr_prices.merge(next_prices, on='Stkcd', suffixes=('_curr', '_next'))
        
        if len(merged) == 0:
            return np.nan
        
        merged['ret'] = (merged['Clsprc_next'] / merged['Clsprc_curr']) - 1
        
        return merged['ret'].mean()


def main():
    print("="*80)
    print("因子投资分析 - 主程序")
    print("="*80)
    
    # 创建分析实例
    fa = FactorAnalysis()
    
    # 运行因子分析
    results = fa.run_factor_analysis()
    
    # 绘制累计收益率曲线
    fa.plot_cumulative_returns()
    
    print("\n" + "="*80)
    print("第一部分：因子投资分析完成！")
    print("="*80)
    
    return fa, results


if __name__ == '__main__':
    fa, results = main()

