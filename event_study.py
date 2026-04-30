"""
事件研究分析 - 红利分配公告的异常收益研究

分析中国A股市场不同类型的红利分配公告在公告日前后是否会产生显著的异常收益
"""

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class EventStudy:
    def __init__(self):
        self.price_data = None
        self.dividend_data = None
        self.industry_dividend_ratio = None
        self.industry_codes = None
        
        self.load_data()
    
    def load_data(self):
        """加载所有必要的数据"""
        print("="*80)
        print("加载事件研究数据")
        print("="*80)
        
        # 1. 加载价格数据
        print("\n1. 加载价格数据...")
        self.load_price_data()
        
        # 2. 加载分红预案数据 (Appendix3)
        print("\n2. 加载分红预案数据...")
        conn = sqlite3.connect('Appendix3.db')
        self.dividend_data = pd.read_sql("SELECT * FROM Appendix3", conn)
        conn.close()
        
        # 转换日期格式
        self.dividend_data['Ppdadt'] = pd.to_datetime(self.dividend_data['Ppdadt'])
        
        # 筛选2015-2024年的数据
        self.dividend_data = self.dividend_data[
            (self.dividend_data['Finyear'] >= 2015) & 
            (self.dividend_data['Finyear'] <= 2024)
        ]
        
        print(f"  分红事件数量: {len(self.dividend_data):,}")
        print(f"  涉及公司数: {self.dividend_data['Stkcd'].nunique()}")
        
        # 3. 加载行业现金分红比例数据
        print("\n3. 加载行业现金分红比例数据...")
        conn = sqlite3.connect('CD_CompOfDivProfitInd.db')
        self.industry_dividend_ratio = pd.read_sql("SELECT * FROM CD_CompOfDivProfitInd", conn)
        conn.close()
        
        # 筛选2015-2024年
        self.industry_dividend_ratio = self.industry_dividend_ratio[
            (self.industry_dividend_ratio['DivdendYear'] >= 2015) & 
            (self.industry_dividend_ratio['DivdendYear'] <= 2024)
        ]
        
        print(f"  行业分红数据: {len(self.industry_dividend_ratio):,} 条")
        
        # 4. 加载上市公司行业代码
        print("\n4. 加载上市公司行业代码...")
        conn = sqlite3.connect('STK_LISTEDCOINFOANL.db')
        self.industry_codes = pd.read_sql("SELECT * FROM STK_LISTEDCOINFOANL", conn)
        conn.close()
        
        # 转换日期
        self.industry_codes['EndDate'] = pd.to_datetime(self.industry_codes['EndDate'])
        
        # 取每个公司最新的行业代码
        self.industry_codes = self.industry_codes.sort_values('EndDate').groupby('Symbol').tail(1)
        
        print(f"  公司行业映射: {len(self.industry_codes):,} 条")
    
    def load_price_data(self):
        """加载价格数据"""
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
        
        self.price_data = pd.concat(dfs, ignore_index=True)
        self.price_data['Trddt'] = pd.to_datetime(self.price_data['Trddt'])
        self.price_data = self.price_data.sort_values(['Stkcd', 'Trddt'])
        
        # 计算日收益率
        self.price_data['ret'] = self.price_data.groupby('Stkcd')['Clsprc'].pct_change()
        
        print(f"  价格数据: {len(self.price_data):,} 条")
        print(f"  日期范围: {self.price_data['Trddt'].min()} 到 {self.price_data['Trddt'].max()}")
    
    def classify_events(self):
        """
        分类事件:
        - 利好事件: 行业现金分红比例 < 60%, 公司宣布分红
        - 利空事件: 行业现金分红比例 > 80%, 公司宣布不分配不转增
        """
        print("\n" + "="*80)
        print("分类事件")
        print("="*80)
        
        # 合并行业代码
        events = self.dividend_data.merge(
            self.industry_codes[['Symbol', 'IndustryCode']], 
            left_on='Stkcd', 
            right_on='Symbol', 
            how='left'
        )
        
        # 合并行业分红比例
        events = events.merge(
            self.industry_dividend_ratio[['DivdendYear', 'IndustryCode', 'DivdendToProfitableRate']], 
            left_on=['Finyear', 'IndustryCode'], 
            right_on=['DivdendYear', 'IndustryCode'], 
            how='left'
        )
        
        print(f"\n合并后事件数: {len(events):,}")
        print(f"有行业信息的事件: {events['IndustryCode'].notna().sum():,}")
        print(f"有分红比例信息的事件: {events['DivdendToProfitableRate'].notna().sum():,}")
        
        # 判断是否分红
        events['is_dividend'] = events['Ppcont'].str.contains('派|分红|现金', na=False)
        events['is_no_dividend'] = events['Ppcont'].str.contains('不分配不转增|不派|不分配', na=False)
        
        # 分类事件
        # 利好事件: 行业分红比例 < 60%, 公司宣布分红
        good_events = events[
            (events['DivdendToProfitableRate'] < 60) & 
            (events['is_dividend'] == True)
        ].copy()
        
        # 利空事件: 行业分红比例 > 80%, 公司宣布不分配不转增
        bad_events = events[
            (events['DivdendToProfitableRate'] > 80) & 
            (events['is_no_dividend'] == True)
        ].copy()
        
        print(f"\n【事件分类结果】")
        print(f"利好事件 (行业分红比例<60%, 公司分红): {len(good_events):,} 个")
        print(f"利空事件 (行业分红比例>80%, 公司不分配): {len(bad_events):,} 个")
        
        self.good_events = good_events
        self.bad_events = bad_events
        
        return good_events, bad_events
    
    def calculate_abnormal_returns(self, events, event_type='good', 
                                   event_window=(-10, 10), estimation_window=(-100, -11)):
        """
        计算异常收益率
        
        Parameters:
        - events: 事件数据
        - event_type: 事件类型 ('good' 或 'bad')
        - event_window: 事件窗口 [-10, 10]
        - estimation_window: 估计窗口 [-100, -11]
        """
        print(f"\n计算{event_type}事件的异常收益率...")
        print(f"  事件窗口: {event_window}")
        print(f"  估计窗口: {estimation_window}")
        
        ar_results = []
        
        for idx, event in events.iterrows():
            stkcd = event['Stkcd']
            event_date = event['Ppdadt']
            
            # 获取该股票的价格数据
            stock_data = self.price_data[self.price_data['Stkcd'] == stkcd].copy()
            
            if len(stock_data) == 0:
                continue
            
            # 找到事件日
            stock_data['days_from_event'] = (stock_data['Trddt'] - event_date).dt.days
            
            # 估计窗口数据
            estimation_data = stock_data[
                (stock_data['days_from_event'] >= estimation_window[0]) & 
                (stock_data['days_from_event'] <= estimation_window[1])
            ]
            
            if len(estimation_data) < 30:  # 至少需要30个交易日
                continue
            
            # 计算估计窗口的平均收益率
            expected_return = estimation_data['ret'].mean()
            
            # 事件窗口数据
            event_data = stock_data[
                (stock_data['days_from_event'] >= event_window[0]) & 
                (stock_data['days_from_event'] <= event_window[1])
            ]
            
            if len(event_data) == 0:
                continue
            
            # 计算异常收益率
            for _, day in event_data.iterrows():
                ar = day['ret'] - expected_return
                
                ar_results.append({
                    'Stkcd': stkcd,
                    'EventDate': event_date,
                    'TradingDate': day['Trddt'],
                    'DaysFromEvent': day['days_from_event'],
                    'Return': day['ret'],
                    'ExpectedReturn': expected_return,
                    'AbnormalReturn': ar
                })
            
            if (idx + 1) % 500 == 0:
                print(f"  处理进度: {idx + 1}/{len(events)}")
        
        ar_df = pd.DataFrame(ar_results)
        print(f"\n完成! 共计算 {len(ar_df):,} 个异常收益观测值")
        
        return ar_df
    
    def calculate_aar_caar(self, ar_df, event_window=(-10, 10)):
        """
        计算AAR (Average Abnormal Return) 和 CAAR (Cumulative AAR)
        """
        print("\n计算AAR和CAAR...")
        
        # 计算每天的AAR
        aar = ar_df.groupby('DaysFromEvent')['AbnormalReturn'].mean().sort_index()
        
        # 筛选事件窗口范围内的数据
        aar = aar[(aar.index >= event_window[0]) & (aar.index <= event_window[1])]
        
        # 计算CAAR
        caar = aar.cumsum()
        
        # 计算标准误和t统计量
        aar_stats = ar_df.groupby('DaysFromEvent')['AbnormalReturn'].agg([
            ('AAR', 'mean'),
            ('StdErr', lambda x: x.std() / np.sqrt(len(x))),
            ('N', 'count')
        ]).sort_index()
        
        aar_stats = aar_stats[
            (aar_stats.index >= event_window[0]) & 
            (aar_stats.index <= event_window[1])
        ]
        
        aar_stats['t_stat'] = aar_stats['AAR'] / aar_stats['StdErr']
        aar_stats['p_value'] = 2 * (1 - stats.t.cdf(np.abs(aar_stats['t_stat']), aar_stats['N'] - 1))
        aar_stats['CAAR'] = aar_stats['AAR'].cumsum()
        
        return aar_stats
    
    def plot_aar_caar(self, aar_stats_good, aar_stats_bad):
        """绘制AAR和CAAR图表"""
        print("\n绘制AAR和CAAR图表...")
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 利好事件 - AAR
        ax1 = axes[0, 0]
        ax1.bar(aar_stats_good.index, aar_stats_good['AAR'], alpha=0.7, color='green')
        ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=1, label='事件日')
        ax1.set_title('利好事件 - 平均异常收益率(AAR)', fontsize=14, fontweight='bold')
        ax1.set_xlabel('事件日相对天数', fontsize=12)
        ax1.set_ylabel('AAR', fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 利好事件 - CAAR
        ax2 = axes[0, 1]
        ax2.plot(aar_stats_good.index, aar_stats_good['CAAR'], linewidth=2, color='green', marker='o')
        ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax2.axvline(x=0, color='red', linestyle='--', linewidth=1, label='事件日')
        ax2.fill_between(aar_stats_good.index, 0, aar_stats_good['CAAR'], alpha=0.3, color='green')
        ax2.set_title('利好事件 - 累积平均异常收益率(CAAR)', fontsize=14, fontweight='bold')
        ax2.set_xlabel('事件日相对天数', fontsize=12)
        ax2.set_ylabel('CAAR', fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 利空事件 - AAR
        ax3 = axes[1, 0]
        ax3.bar(aar_stats_bad.index, aar_stats_bad['AAR'], alpha=0.7, color='red')
        ax3.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax3.axvline(x=0, color='red', linestyle='--', linewidth=1, label='事件日')
        ax3.set_title('利空事件 - 平均异常收益率(AAR)', fontsize=14, fontweight='bold')
        ax3.set_xlabel('事件日相对天数', fontsize=12)
        ax3.set_ylabel('AAR', fontsize=12)
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # 利空事件 - CAAR
        ax4 = axes[1, 1]
        ax4.plot(aar_stats_bad.index, aar_stats_bad['CAAR'], linewidth=2, color='red', marker='o')
        ax4.axhline(y=0, color='black', linestyle='--', linewidth=0.8)
        ax4.axvline(x=0, color='red', linestyle='--', linewidth=1, label='事件日')
        ax4.fill_between(aar_stats_bad.index, 0, aar_stats_bad['CAAR'], alpha=0.3, color='red')
        ax4.set_title('利空事件 - 累积平均异常收益率(CAAR)', fontsize=14, fontweight='bold')
        ax4.set_xlabel('事件日相对天数', fontsize=12)
        ax4.set_ylabel('CAAR', fontsize=12)
        ax4.legend()
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('event_study_aar_caar.png', dpi=300, bbox_inches='tight')
        print("AAR和CAAR图表已保存: event_study_aar_caar.png")
        
        return fig
    
    def analyze_specific_days(self, ar_df, event_type='good', days=[0, 7, 30]):
        """
        分析特定日期(T+0, T+7, T+30)的异常收益统计
        """
        print(f"\n分析{event_type}事件在特定日期的异常收益...")
        
        results = []
        
        for day in days:
            # 筛选该日的数据
            day_data = ar_df[ar_df['DaysFromEvent'] == day]['AbnormalReturn']
            
            if len(day_data) == 0:
                continue
            
            # 计算统计量
            mean_ar = day_data.mean()
            var_ar = day_data.var()
            std_err = day_data.std() / np.sqrt(len(day_data))
            
            # t检验
            t_stat = mean_ar / std_err if std_err > 0 else 0
            p_value = 2 * (1 - stats.t.cdf(np.abs(t_stat), len(day_data) - 1))
            
            results.append({
                'Day': f'T+{day}',
                'Mean_AR': mean_ar,
                'Variance': var_ar,
                'StdErr': std_err,
                't_statistic': t_stat,
                'p_value': p_value,
                'N': len(day_data),
                'Significant': '***' if p_value < 0.01 else ('**' if p_value < 0.05 else ('*' if p_value < 0.1 else ''))
            })
        
        results_df = pd.DataFrame(results)
        
        print(f"\n【{event_type}事件 - 特定日期异常收益统计】")
        print(results_df.to_string(index=False))
        
        return results_df
    
    def run_event_study(self):
        """运行完整的事件研究"""
        print("\n" + "="*80)
        print("开始事件研究分析")
        print("="*80)
        
        # 1. 分类事件
        good_events, bad_events = self.classify_events()
        
        # 2. 计算异常收益率
        print("\n" + "="*80)
        print("计算异常收益率")
        print("="*80)
        
        ar_good = self.calculate_abnormal_returns(
            good_events, 
            event_type='利好', 
            event_window=(-10, 10),
            estimation_window=(-100, -11)
        )
        
        ar_bad = self.calculate_abnormal_returns(
            bad_events, 
            event_type='利空', 
            event_window=(-10, 10),
            estimation_window=(-100, -11)
        )
        
        # 3. 计算AAR和CAAR
        print("\n" + "="*80)
        print("计算AAR和CAAR")
        print("="*80)
        
        aar_stats_good = self.calculate_aar_caar(ar_good, event_window=(-10, 10))
        aar_stats_bad = self.calculate_aar_caar(ar_bad, event_window=(-10, 10))
        
        print("\n【利好事件 - CAAR统计】")
        print(aar_stats_good[['AAR', 'CAAR', 't_stat', 'p_value']].head(10).to_string())
        
        print("\n【利空事件 - CAAR统计】")
        print(aar_stats_bad[['AAR', 'CAAR', 't_stat', 'p_value']].head(10).to_string())
        
        # 4. 绘制AAR和CAAR图表
        self.plot_aar_caar(aar_stats_good, aar_stats_bad)
        
        # 5. 分析特定日期
        print("\n" + "="*80)
        print("分析特定日期的异常收益")
        print("="*80)
        
        specific_days_good = self.analyze_specific_days(ar_good, event_type='利好', days=[0, 7, 30])
        specific_days_bad = self.analyze_specific_days(ar_bad, event_type='利空', days=[0, 7, 30])
        
        # 6. 投资策略建议
        print("\n" + "="*80)
        print("投资策略建议")
        print("="*80)
        
        self.summarize_findings(aar_stats_good, aar_stats_bad, specific_days_good, specific_days_bad)
        
        return {
            'ar_good': ar_good,
            'ar_bad': ar_bad,
            'aar_stats_good': aar_stats_good,
            'aar_stats_bad': aar_stats_bad,
            'specific_days_good': specific_days_good,
            'specific_days_bad': specific_days_bad
        }
    
    def summarize_findings(self, aar_stats_good, aar_stats_bad, specific_good, specific_bad):
        """总结研究发现并提出投资策略"""
        
        # 利好事件分析
        caar_t10_good = aar_stats_good.loc[10, 'CAAR'] if 10 in aar_stats_good.index else 0
        caar_t0_good = aar_stats_good.loc[0, 'CAAR'] if 0 in aar_stats_good.index else 0
        
        # 利空事件分析
        caar_t10_bad = aar_stats_bad.loc[10, 'CAAR'] if 10 in aar_stats_bad.index else 0
        caar_t0_bad = aar_stats_bad.loc[0, 'CAAR'] if 0 in aar_stats_bad.index else 0
        
        print("\n【主要发现】")
        print(f"\n1. 利好事件（行业低分红比例下的分红公告）:")
        print(f"   - 事件窗口[-10, 10]的累积异常收益(CAAR): {caar_t10_good:.4%}")
        print(f"   - 事件日(T+0)的AAR: {aar_stats_good.loc[0, 'AAR']:.4%}" if 0 in aar_stats_good.index else "")
        print(f"   - 统计显著性: {'显著' if aar_stats_good.loc[0, 'p_value'] < 0.05 else '不显著'}" if 0 in aar_stats_good.index else "")
        
        print(f"\n2. 利空事件（行业高分红比例下的不分红公告）:")
        print(f"   - 事件窗口[-10, 10]的累积异常收益(CAAR): {caar_t10_bad:.4%}")
        print(f"   - 事件日(T+0)的AAR: {aar_stats_bad.loc[0, 'AAR']:.4%}" if 0 in aar_stats_bad.index else "")
        print(f"   - 统计显著性: {'显著' if aar_stats_bad.loc[0, 'p_value'] < 0.05 else '不显著'}" if 0 in aar_stats_bad.index else "")
        
        print(f"\n【可行的投资策略】")
        
        if caar_t10_good > 0.01:  # 正向显著
            print("\n策略1: 利好事件套利策略")
            print("  - 时机: 监控行业分红比例<60%的行业，当公司宣布分红预案时")
            print("  - 操作: 在公告日或之前买入，持有至T+7或T+10")
            print(f"  - 预期收益: 约{caar_t10_good:.2%}")
            print("  - 风险提示: 需要快速反应，流动性风险")
        
        if caar_t10_bad < -0.01:  # 负向显著
            print("\n策略2: 利空事件对冲策略")
            print("  - 时机: 监控行业分红比例>80%的行业公司")
            print("  - 操作: 当宣布不分红时，考虑做空或减持")
            print(f"  - 预期收益: 约{-caar_t10_bad:.2%}")
            print("  - 风险提示: A股做空机制有限，可考虑期权对冲")
        
        print("\n策略3: 行业轮动策略")
        print("  - 逻辑: 关注行业分红政策的差异")
        print("  - 操作: 配置低分红率行业中的高分红股票，规避高分红率行业的低分红股票")
        print("  - 优势: 利用市场对分红政策的预期差")
        
        print("\n策略4: 事件驱动量化策略")
        print("  - 建立分红事件监控系统")
        print("  - 结合行业分红比例、公司基本面、技术指标")
        print("  - 设置自动交易触发条件")
        print("  - 严格风控，设置止损止盈")


def main():
    print("="*80)
    print("事件研究分析 - 主程序")
    print("="*80)
    
    # 创建事件研究实例
    es = EventStudy()
    
    # 运行事件研究
    results = es.run_event_study()
    
    print("\n" + "="*80)
    print("第二部分：事件研究分析完成！")
    print("="*80)
    
    return es, results


if __name__ == '__main__':
    es, results = main()

