import os
from S3Work import S3Facilities
import pandas as pd
from datetime import datetime, date
import matplotlib.pyplot as plt

def extract_infos(df):
    df['Model Info'] = df['Brand'] + ' ' + df['Model'] + ' ' + df['Year']
    df = df[['Model Info', 'Price']]

    df_models_count = df['Model Info'].value_counts().reset_index()

    df_models_count.columns = ['Model Info', 'Count']

    df['Price'] = [float(i.replace('R$ ', '').replace('.', '')) for i in df['Price']]
    models_mean_prices = df.groupby('Model Info')['Price'].mean().reset_index()
    models_mean_prices.columns = ['Model Info', 'MeanPrice']

    models_result = pd.merge(df_models_count, models_mean_prices, on='Model Info')
    ranking = models_result.sort_values('Count', ascending=False)['Model Info'][:10]

    return ranking

def extract_timeseries_infos(entire_df, ranking):
    entire_df = entire_df.groupby('Model Info')

    final_df = pd.DataFrame()

    for group_name, df in entire_df:
        if group_name in ranking.values:
            this_df = df.groupby(df.index)[['Price']].median()
            this_df.rename(columns={'Price':group_name}, inplace=True)
            final_df = pd.concat([final_df, this_df], axis=1)
    
    return final_df

def plot_time_series(timeserie):
    for col in timeserie.columns:
        this_plot_df = timeserie[[col]]
        this_plot_df.plot(figsize=(12, 6), title=f'Localiza - {col}')
        plt.xlabel('Date')
        plt.ylabel('Price (R$)')
        plt.xticks(rotation=45)
        plt.legend(loc='upper left', bbox_to_anchor=(1.0, 1.0))

def update_data(listed_files, locadora):
    filenames = [i for i in listed_files if locadora in i]

    actual_df = s3.get_object(f'used-cars-for-sale/full_data/{locadora}/{locadora}.csv', index_col=0)
    for fn in filenames:
        this_date = fn.split('/')[-1].split('.')[0]
        if this_date not in actual_df.index:
            this_df = pd.DataFrame(s3.get_object(fn))
            this_df.index = [this_date]*len(this_df)
            actual_df = pd.concat([actual_df, this_df])
    s3.put_file(actual_df, f'used-cars-for-sale/full_data/{locadora}/{locadora}.csv')

    return actual_df

if __name__ == "__main__":
    s3 = S3Facilities('alternative-market-data', 'us-east-1')

    listed_files = s3.list_files('used-cars-for-sale/full_data', endswith='.json')

    localiza_df = update_data(listed_files, 'localiza')
    movida_df = update_data(listed_files, 'movida')
    unidas_df = update_data(listed_files, 'unidas')

    # localiza_models = extract_infos(localiza_df)
    # movida_models = extract_infos(movida_df)
    # unidas_models = extract_infos(unidas_df)

    # ranking_localiza = localiza_models.sort_values('Count', ascending=False)['Model Info'][:10]
    # ranking_unidas = movida_models.sort_values('Count', ascending=False)['Model Info'][:10]
    # ranking_movida = unidas_models.sort_values('Count', ascending=False)['Model Info'][:10]

    # localiza_ts = extract_timeseries_infos(localiza_df, ranking_localiza)
    # unidas_ts = extract_timeseries_infos(unidas_df, ranking_unidas)
    # movida_ts = extract_timeseries_infos(movida_df, ranking_movida)
