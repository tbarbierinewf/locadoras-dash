import os, time
import boto3, botocore
import pandas as pd
import textdistance
import numpy as np

from unidecode import unidecode
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

class FipeScraper(object):
    def __init__(self, timeout=3):
        self.page_count = 1
        self.timeout = timeout
        self.url = 'https://www.tabelafipebrasil.com/carros'
        self.soup = None
        self.setUp()

    def setUp(self):
        '''Setting up selenium driver. This functions has an extra chrome option for setting the default download directory to the /tmp/ path.'''
        caps = DesiredCapabilities.CHROME.copy()
        caps["pageLoadStrategy"] = "normal"
        
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')

        # options.add_argument('--no-sandbox')
        # options.add_argument('--headless')
        # options.add_argument('--disable-gpu')
        # options.add_argument('--disable-dev-shm-usage')
        # options.add_argument('--disable-dev-tools')
        # options.add_argument('--remote-debugging-port=9222')
        # options.add_argument('--window-size=1280x1696')
        # options.add_argument('--user-data-dir=/tmp/chrome-user-data')
        # options.add_argument('--single-process')
        # options.add_argument("--no-zygote")
        # options.add_argument('--ignore-certificate-errors')

        # options.binary_location = os.environ['CHROME_BINARY_PATH']      

        # service = Service(executable_path=os.environ['CHROME_DRIVER_PATH'])
        # self.driver = webdriver.Chrome(service=service, options=options)
        self.driver = webdriver.Chrome(options=options)

    def formatar_data(self, mes, ano):
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
    
    def get(self, url:str = None):
        if url == None:
            full_url = f"{self.url}"
        else:
            full_url = url
        response = self.driver.get(full_url)
        return response

    def refresh_page(self):
        self.driver.refresh()

    def open_consulta(self):
        consultar_carro = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//li[@class='ilustra']/a[@data-label='carro']")))
        self.driver.execute_script("arguments[0].click();", consultar_carro)

    def set_tipo_veiculo(self):
        print('Definindo veículo')
        seletor = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='sel-tipo']"))))
        seletor.select_by_value('A')

    def set_mes_referencia(self, mes, ano):
        print('Definindo mes referencia')
        ativar_seletor = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='selectTabelaReferenciacarro']"))))
        ativar_seletor.select_by_visible_text(self.formatar_data(int(mes), ano))

    def set_marca(self, marca:str):
        print('Definindo marca')
        elements = WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@class='pure-u-1-2 pure-u-md-1-2 pure-u-lg-1-3 fipe_link']/a")))
        
        to_open = None

        for element in elements:
            link = element.get_attribute('href')
            if marca.lower() in link.lower():
                to_open = link
                break
        self.driver.get(to_open)

    def set_modelo(self, modelo:str):
        print('Definindo modelo')
        elements = WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//table//a")))

        all_models = {'Link':[], 'Score':[]}
        for element in elements:
            this_href = element.get_attribute('href')
            this_model = this_href.split('/')[-1].replace('-', ' ')

            score = textdistance.levenshtein(modelo.lower(), this_model.lower())

            all_models['Link'].append(this_href)
            all_models['Score'].append(score)
        
        return pd.DataFrame(all_models).drop_duplicates().sort_values('Score', ascending=True)

    def set_ano(self, ano:str):
        print('Definindo ano')
        elements = WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@class='DIVdetail']//table//a")))

        for element in elements:
            href = element.get_attribute('href')
            if ano in href and 'diesel' not in href.lower():
                return href
        return None

    def search(self):
        search_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//div[@class='button pesquisa']/a[@id='buttonPesquisarcarro']")))
        self.driver.execute_script("arguments[0].click();", search_button)
    
    def get_table(self, ano, mes):
        print('Extraindo tabela')
        table = WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//div[@class='site-content']//table[@style='width:100%']")))[0]
        table_html = table.get_attribute('outerHTML')
        df = pd.read_html(table_html, header=0)
        df.index = df[0].str.rstrip(':')
        df.index = [i.lower() for i in df.index]
        print(df)
        out = df.loc[self.formatar_data(mes, ano)]
        print(out)
        return out

    def search_price(self, df_selected:pd.DataFrame, month, year, locadora):
        final_df = pd.DataFrame()
        for i, row in df_selected.iterrows():
            sel = row['Model Info']

            self.get()
            self.set_tipo_veiculo()
            self.set_marca(row['Brand'])

            if locadora == 'Localiza':
                links_modelos = self.set_modelo(row['Model'])
            else:
                links_modelos = self.set_modelo(row['Model'] + row['Specification'])

            found = None
            for link in links_modelos['Link'].values:
                self.get(link)
                found = self.set_ano(row['Year'].split('/')[0])
                if found != None:
                    print('Found:', found)
                    break

            self.get(found)
            final_df = pd.concat([final_df, pd.DataFrame({sel, self.get_table(year, month)})]) 

        self.driver.close()
        return final_df