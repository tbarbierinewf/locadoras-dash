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
        self.url = 'https://veiculos.fipe.org.br/'
        self.soup = None
        self.setUp()
        self.get()
        self.open_consulta()

    def setUp(self):
        '''Setting up selenium driver. This functions has an extra chrome option for setting the default download directory to the /tmp/ path.'''
        caps = DesiredCapabilities.CHROME.copy()
        caps["pageLoadStrategy"] = "normal"
        
        options = Options()
        options.add_argument('--disable-blink-features=AutomationControlled')

        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-dev-tools')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--window-size=1280x1696')
        options.add_argument('--user-data-dir=/tmp/chrome-user-data')
        options.add_argument('--single-process')
        options.add_argument("--no-zygote")
        options.add_argument('--ignore-certificate-errors')

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
        
        data_formatada = f"{nomes_meses[mes]}/{ano}"
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

    def set_mes_referencia(self, mes, ano):
        ativar_seletor = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='selectTabelaReferenciacarro']"))))
        ativar_seletor.select_by_visible_text(self.formatar_data(int(mes), ano))

    def set_marca(self, marca:str):
        
        selector = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='selectMarcacarro']"))))
        option_to_select = [i.get_attribute('innerHTML') for i in selector.options if marca.lower() in unidecode(i.get_attribute('innerHTML').lower())]
        selector.select_by_visible_text(option_to_select[0])

    def set_modelo(self, modelo:str):
        selector = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='selectAnoModelocarro']"))))
        min_value = np.inf

        for opt in selector.options:
            score = textdistance.levenshtein(modelo.lower(), unidecode(opt.get_attribute('innerHTML').lower()))
            if score < min_value:
                option_to_select = opt.get_attribute('innerHTML')
                min_value = score
        selector.select_by_visible_text(option_to_select)

    def set_ano(self, ano:str):
        selector = Select(WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@id='selectAnocarro']"))))
        self.driver.execute_script("arguments[0].click();", selector)
        option_to_select = [i.get_attribute('innerHTML') for i in selector.options if ano in i.get_attribute('innerHTML') and 'diesel' not in i.get_attribute('innerHTML').lower()]
        selector.select_by_visible_text(option_to_select[0])

    def search(self):
        search_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//div[@class='button pesquisa']/a[@id='buttonPesquisarcarro']")))
        self.driver.execute_script("arguments[0].click();", search_button)
    
    def get_table(self):
        table = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@id='resultadoConsultacarroFiltros']/table")))
        table_html = table.get_attribute('outerHTML')
        df = pd.read_html(table_html)[0]
        df.index = df[0].str.rstrip(':')
        df = df.drop(columns=0)
        column_name = df.loc['Modelo', 1]
        df = df.drop('Modelo')
        df.columns = [column_name]

        return df

    def search_price(self, df_selected:pd.DataFrame, month, year):
        final_df = {}
        for i, row in df_selected.iterrows():
            sel = row['Model Info']
            self.set_mes_referencia(month, year)
            self.set_marca(row['Brand'])
            self.set_modelo(row['Model'])
            self.set_ano(row['Year'].split('/')[0])
            self.search()
            df = self.get_table().loc['Preço Médio']
            final_df[sel] = df

        self.driver.close()
        return pd.DataFrame(final_df)

