# analytics.py
import io
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

plt.switch_backend('Agg') 

def create_db_engine(database_url):
    return create_engine(database_url, future=True)

def query_prices(engine, tickers=None, start_date=None, end_date=None):
    
    if isinstance(tickers, str):
        tickers = [tickers]
    
    q = "SELECT * FROM stock_data WHERE 1=1"
    params={}

    if tickers:
        q += " AND upper(\"Ticker\") IN :tickers"
        params['tickers'] = tuple(t.upper() for t in tickers)

    if start_date:
        q += f" AND \"Date\" >= TO_DATE('{start_date}', 'YYYY-MM-DD')"
        params['start_date'] = start_date
    
    if end_date:
        q += f" AND \"Date\" <= TO_DATE('{end_date}', 'YYYY-MM-DD')"
        params['end_date'] = end_date
    
    df = pd.read_sql(text(q), engine, params=params)
    df['Date'] = pd.to_datetime(df['Date'])
    return df.sort_values(by = 'Date').reset_index(drop=True)

def compute_stats(df: pd.DataFrame):

    if df.empty:
        return None

    results = {}

    for ticker, group in df.groupby("Ticker"):
        g = group.sort_values("Date")

        stats = {
            "ticker": ticker,
            "mean_close": float(g["Close"].mean()),
            "min_close": float(g["Close"].min()),
            "max_close": float(g["Close"].max()),
            "start_price": float(g["Close"].iloc[0]),
            "end_price": float(g["Close"].iloc[-1]),
        }

        stats["change_abs"] = stats["end_price"] - stats["start_price"]
        stats["change_pct"] = (
            stats["change_abs"] / stats["start_price"] * 100
            if stats["start_price"] != 0
            else None
        )

        stats["volatility"] = float(g["Close"].pct_change().dropna().std())

        results[ticker] = stats

    if len(results) == 1:
        return list(results.values())[0]

    return results

def plot_price_chart(df: pd.DataFrame):

    plt.figure(figsize=(12, 6))

    for ticker, group in df.groupby("Ticker"):
        plt.plot(
            group["Date"],
            group["Close"],
            label=f"{group['Brand_Name'].iloc[0]} ({ticker})"
        )

    plt.title(f"Динамика цен акций {', '.join(list(df.Brand_Name.unique()))}")
    plt.xlabel("Дата")
    plt.ylabel("Цена закрытия")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)

    return buf


def format_stats(stats):
    if not stats:
        return "Нет данных для анализа."
    
    if len(stats) == 1:
        formatted_stats = (
            f"Аналитика по тикеру {stats['ticker']} за указанный период:\n\n"
            f"Средняя цена закрытия:  {stats['mean_close']:.2f}\n"
            f"Минимальная цена закрытия:  {stats['min_close']:.2f}\n"
            f"Максимальная цена закрытия:  {stats['max_close']:.2f}\n"
            f"Цена на начало периода:  {stats['start_price']:.2f}\n"
            f"Цена на конец периода:  {stats['end_price']:.2f}\n"
            f"Изменение цены:  {stats['change_abs']:.2f} ({stats['change_pct']:.2f}%)\n"
            f"Волатильность:  {stats['volatility']:.4f}\n"
        )
        
        if stats['change_abs'] > 0:
            formatted_stats += "\nЦены росли."
        elif stats['change_abs'] < 0:
            formatted_stats += "\nЦены упали."
        else:
            formatted_stats += "\nЦены остались без изменения."

        return formatted_stats
        
    else:
        mes = []
        for st in stats.keys():
            formatted_stats = (
                f"Аналитика по тикеру {stats[st]['ticker']} за указанный период:\n\n"
                f"Средняя цена закрытия:  {stats[st]['mean_close']:.2f}\n"
                f"Минимальная цена закрытия:  {stats[st]['min_close']:.2f}\n"
                f"Максимальная цена закрытия:  {stats[st]['max_close']:.2f}\n"
                f"Цена на начало периода:  {stats[st]['start_price']:.2f}\n"
                f"Цена на конец периода:  {stats[st]['end_price']:.2f}\n"
                f"Изменение цены:  {stats[st]['change_abs']:.2f} ({stats[st]['change_pct']:.2f}%)\n"
                f"Волатильность:  {stats[st]['volatility']:.4f}\n"
                f"\n"
            )
            
            if stats[st]['change_abs'] > 0:
                formatted_stats += "\nЦены росли."
            elif stats[st]['change_abs'] < 0:
                formatted_stats += "\nЦены упали."
            else:
                formatted_stats += "\nЦены остались без изменения."
            mes.append(formatted_stats)
        return '\n'.join(mes)