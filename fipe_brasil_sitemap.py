import pandas as pd
import textdistance
from io import StringIO

from urllib.request import Request, urlopen
from urllib.parse import urlparse
from bs4 import BeautifulSoup

def float_to_currency(value_float:float):
    value_str = "{:,.2f}".format(value_float)
    return "R$ " + value_str


def currency_to_float(value_str:str):
    return float(value_str.replace("R$", "").strip().replace(".", "").replace(",", "."))
    
class FipeScraper(object):
    def __init__(self, url:str=None, timeout=3):
        self.page_count = 1
        self.timeout = timeout

        if url == None:
            self.url = 'https://www.tabelafipebrasil.com/sitemaps/sitemap_model_yearA.xml'
        else:
            self.url = url

        self.sitemap = self.get_sitemap()
        self.links = self.get_links()

    def formatar_data(self, ano, mes):
        nomes_meses = {
            1: 'janeiro',
            2: 'fevereiro',
            3: 'março',
            4: 'abril',
            5: 'maio',
            6: 'junho',
            7: 'julho',
            8: 'agosto',
            9: 'setembro',
            10: 'outubro',
            11: 'novembro',
            12: 'dezembro'
        }
        
        if mes < 1 or mes > 12:
            return "Mês inválido"
        
        data_formatada = f"{nomes_meses[mes]} {ano}"
        return data_formatada
    
    def get_sitemap(self, url:str=None):
        if url == None:
            url = self.url
        
        req = Request(url)
        req.add_header('user-agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36")
        response = urlopen(req)
        xml = BeautifulSoup(response, 'lxml', from_encoding=response.info().get_param('charset'))

        return xml
    
    def get_this_price(self, url_list:str, ano, mes):
        for url in url_list:
            req = Request(url)
            req.add_header('user-agent', "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36")
            response = urlopen(req).read()
            soup = BeautifulSoup(response, 'html.parser')
            html_table = soup.find('table', {'style': 'width:100%'})
            table = pd.read_html(StringIO(str(html_table)), header=0)[0]
            table = table[['Mês', 'Valor']]
            table.index = table.pop('Mês')
            table.index = [i.lower() for i in table.index]
            try:
                value = table.loc[self.formatar_data(ano, mes)]['Valor']
                return value, url.split('/')[5].replace('-', ' ')
            except:
                pass
        return None

    def get_links(self, xml:str=None):
        if xml == None:
            xml = self.sitemap
        loc_elements = xml.find_all('loc')
        loc_texts = [loc.text for loc in loc_elements]
        return loc_texts

    def get_more_probable(self, modelo, links):
        all_models = {'Links':[], 'Score':[]}
        for link in links:
            this_model = link.split('/')[5].replace('-', ' ')

            score = textdistance.jaccard(modelo.lower().replace('.', '').replace('-', ' '), this_model.lower())

            all_models['Links'].append(link)
            all_models['Score'].append(score)
        
        sorted_df = pd.DataFrame(all_models).drop_duplicates().sort_values('Score', ascending=False)
        return sorted_df['Links'].values
    
    def search_price(self, df_selected:pd.DataFrame, ano_ref, mes, locadora):
        # Tamanho padrão: 7
        # 4: marca; 5: modelo; 6: ano

        data = {'Rank':[], 'Model':[], 'Price':[], 'Collected Price':[], 'Price Diff':[], 'Reference Model':[]}
        for i, row in df_selected.iterrows():
            sel = row['Model Info']

            marca = row['Brand']
            if locadora == 'Localiza':
                modelo = row['Model']
            else:
                modelo = row['Model'] + ' ' + row['Specification']
            
            modelo_ano = row['Year'].split('/')[0]

            this_possibilities = [i for i in self.links if marca.lower() in i.split('/')[4].lower() and modelo_ano in i.split('/')[-1]]
            most_probables = self.get_more_probable(modelo, this_possibilities)
            price, reference = self.get_this_price(most_probables, ano_ref, mes)
            float_price = currency_to_float(price)

            data['Rank'].append(row['Posição'])
            data['Model'].append(modelo)
            data['Price'].append(price)
            data['Collected Price'].append(float_to_currency(row['Median Prices']))
            data['Price Diff'].append("{:.2f} %".format(-(float_price - row['Median Prices'])/(float_price)*100))
            data['Reference Model'].append(reference)
        
        return pd.DataFrame(data)
            

