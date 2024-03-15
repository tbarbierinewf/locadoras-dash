import streamlit as st
import pandas as pd
import altair as alt
from S3Work import S3Facilities
from fipe_brasil_sitemap import FipeScraper
from datetime import date, timedelta

def get_ranking(df:pd.DataFrame, selected_locadora:str):
    this_df = pd.DataFrame()
    this_grouped = df.groupby('Model Info')

    this_df['Sales'] = this_grouped['Price'].count()

    df['Price'] = [float(i.replace('R$ ', '').replace('.', '')) for i in df['Price']]
    this_df['Median Prices'] = this_grouped['Price'].median()

    this_df['Last Prices'] = this_grouped['Price'].last()

    ranking = this_df.sort_values('Sales', ascending=False)
    ranking.reset_index(inplace=True)

    if selected_locadora == 'Localiza':
        subset = ['Model Info', 'Brand', 'Model', 'Year']
    else:
        subset = ['Model Info', 'Brand', 'Model', 'Specification', 'Year']

    ranking = pd.merge(ranking, df[subset].drop_duplicates(), how='left', on='Model Info')

    ranking['Posição'] = [f"{i}°" for i in range(1, len(ranking) + 1)]

    return ranking[:25]


def extract_timeseries_infos(entire_df, ranking):
    entire_df = entire_df.groupby('Model Info')

    final_df = pd.DataFrame()
    for group_name, df in entire_df:
        if group_name in ranking.values:
            this_df = pd.DataFrame()

            grouped = df.groupby(df.index)
            this_df['Median Price'] = grouped['Price'].median()
            this_df['Sales'] = grouped['Model Info'].count()
            this_df['Car Model'] = [group_name]*len(this_df)
            final_df = pd.concat([final_df, this_df])

    final_df.reset_index(inplace=True)
    final_df.rename(columns={'index':'Date'}, inplace=True)

    return final_df

def dataframe_with_selections(df):
    df_with_selections = df.copy()
    df_with_selections.insert(0, "Select", False)

    edited_df = st.data_editor(
        df_with_selections,
        hide_index=True,
        num_rows='fixed',
        column_config={"Select": st.column_config.CheckboxColumn(required=True)},
        disabled=df.columns,
        column_order=['Select', 'Posição', 'Model Info', 'Sales', 'Median Prices', 'Last Prices'],
        height=560
    )

    selected_rows = edited_df[edited_df.Select]
    return selected_rows.drop('Select', axis=1)

@st.cache_data
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
    st.set_page_config(
        page_title="Locadoras BI",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded")

    alt.themes.enable("dark")


    s3 = S3Facilities('alternative-market-data', 'us-east-1')
    listed_files = s3.list_files('used-cars-for-sale/full_data', endswith='.json')

    localiza_df = update_data(listed_files, 'localiza')
    movida_df = update_data(listed_files, 'movida')
    unidas_df = update_data(listed_files, 'unidas')

    localiza_df.index = pd.to_datetime(localiza_df.index)
    movida_df.index = pd.to_datetime(movida_df.index)
    unidas_df.index = pd.to_datetime(unidas_df.index)

    locadoras_and_data = {'Localiza':localiza_df,
                        'Movida':movida_df,
                        'Unidas':unidas_df}

    with st.sidebar:
        st.title('🚗 Car Prices Dashboard')

        locadoras = ['Localiza', 'Movida', 'Unidas']
        selected_locadora = st.selectbox('Selecione uma Locadora', locadoras, index=len(locadoras)-1)

        this_df = locadoras_and_data[selected_locadora]

        sidebar_col = st.columns((1, 1), gap='small')

        with sidebar_col[0]:
            years_list = sorted(this_df.index.year.unique())
            initial_selected_year = st.selectbox('Ano de início', years_list, index=0)
            final_selected_year = st.selectbox('Ano final', years_list, index=len(years_list)-1)
        
        with sidebar_col[1]:
            initial_months_list = sorted(this_df[this_df.index.year == initial_selected_year].index.month.unique())
            final_months_list = sorted(this_df[this_df.index.year == final_selected_year].index.month.unique())
            initial_selected_month = st.selectbox('Mês de início', initial_months_list, index=0)
            final_selected_month = st.selectbox('Mês final', final_months_list, index=len(final_months_list)-1)
        
        initial_day = 1
        final_day = 31

        while True:
            try:
                first_loc = this_df.index.get_loc(pd.to_datetime(f'{initial_selected_year}-{initial_selected_month:02d}-{initial_day:02d}'))
                if not isinstance(first_loc, int):
                    first_loc = first_loc.start
                break
            except:
                initial_day += 1

        while True:
            try:
                final_loc = this_df.index.get_loc(pd.to_datetime(f'{final_selected_year}-{final_selected_month:02d}-{final_day:02d}'))
                if not isinstance(final_loc, int):
                    final_loc = final_loc.stop + 1
                break
            except:
                final_day -= 1

        df_selected = this_df.iloc[first_loc:final_loc]

        if selected_locadora == 'Localiza':
            df_selected['Model Info'] = df_selected['Brand'] + ' ' + df_selected['Model'] + ' ' + df_selected['Year']
        else:
            df_selected['Model Info'] = df_selected['Brand'] + ' ' + df_selected['Model'] + ' ' + df_selected['Specification'] + ' ' + df_selected['Year']


        # df_selected = df_selected[['Model Info', 'Price']]

    col = st.columns((1, 1), gap='medium')  

    with col[0]:
        st.markdown('#### Ranking')
        this_ranking = get_ranking(df_selected, selected_locadora)
        selection = dataframe_with_selections(this_ranking)['Model Info']

        if not selection.empty:
            this_cols = st.columns(2, gap='small')
            with this_cols[0]:
                st.markdown('### Search for FIPE Prices?')
            with this_cols[1]:
                response = st.button('Search')

            if response:
                scraper = FipeScraper()
                fipe_df = scraper.search_price(this_ranking[this_ranking['Model Info'].isin(selection)], initial_selected_year, initial_selected_month, selected_locadora)
                if not fipe_df.empty:
                    st.dataframe(fipe_df, hide_index=True, use_container_width=True)
                else:
                    st.write('Data not found.')

    with col[1]:
        if not selection.empty:
            time_series = extract_timeseries_infos(df_selected[df_selected['Model Info'].isin(selection)], this_ranking)
            st.markdown('#### Median Price')
            st.altair_chart(alt.Chart(time_series).mark_line().encode(
                x='Date:T',
                y=alt.Y('Median Price:Q', scale=alt.Scale(domain=[min(time_series['Median Price']), max(time_series['Median Price'])])),
                color='Car Model:N'
            ), use_container_width=True)
            st.markdown('#### Sales')
            st.altair_chart(alt.Chart(time_series).mark_line().encode(
                x='Date:T',
                y=alt.Y('Sales:Q', scale=alt.Scale(domain=[min(time_series['Sales']), max(time_series['Sales'])])),
                color='Car Model:N'
            ), use_container_width=True)

    if not selection.empty:
        full_ts = this_df.copy()
        if selected_locadora == 'Localiza':
            full_ts['Model Info'] = full_ts['Brand'] + ' ' + full_ts['Model'] + ' ' + full_ts['Year']
        else:
            full_ts['Model Info'] = full_ts['Brand'] + ' ' + full_ts['Model'] + ' ' + full_ts['Specification'] + ' ' + full_ts['Year']

        full_ts['Price'] = [float(i.replace('R$ ', '').replace('.', '')) for i in full_ts['Price']]

        full_time_series = extract_timeseries_infos(full_ts[full_ts['Model Info'].isin(selection)], this_ranking)
        st.markdown('## Historical series')
        st.markdown('#### Median Price')
        st.altair_chart(alt.Chart(full_time_series).mark_line().encode(
            x='Date:T',
            y=alt.Y('Median Price:Q', scale=alt.Scale(domain=[min(full_time_series['Median Price']), max(full_time_series['Median Price'])])),
            color='Car Model:N'
        ), use_container_width=True)
        st.markdown('#### Sales')
        st.altair_chart(alt.Chart(full_time_series).mark_line().encode(
            x='Date:T',
            y=alt.Y('Sales:Q', scale=alt.Scale(domain=[min(full_time_series['Sales']), max(full_time_series['Sales'])])),
            color='Car Model:N'
        ), use_container_width=True)