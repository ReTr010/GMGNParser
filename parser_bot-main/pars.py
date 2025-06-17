from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By


def parse_elements(chain, address):
    # Настройка веб-драйвера
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.maximize_window()


    if chain.lower() == 'ethereum':
        chain = "eth"

    if chain.lower() == 'solana':
        chain = "sol"

    # Формируем ссылку с параметрами chain и address
    url = f'https://gmgn.ai/{chain}/token/{address}'
    driver.get(url)

    try:
        # Ожидаем и закрываем JS окно, если оно есть
        close_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div[3]/div/section/button'))
        )
        close_button.click()
    except Exception as e:
        print(f"Ошибка при нажатии на крестик: {e}")
    try:
        error_div = driver.find_element(By.XPATH, '//*[@id="__next"]/div/div/main/div[2]')
        error_div_text = error_div.text

        error_texts = [
            "This token has very low liquidity. Be careful when trading!",
            "Might be Honeypot!! Token Frozen blacklist enabled."
        ]
        has_error = any(error_text in error_div_text for error_text in error_texts)
        print("Ошибки найдены:", has_error)

    except:
        print("Элемент main/div[2] не найден")
    if has_error == True:
        error_div = 3
    else: error_div = 2
    selectors = [
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[2]',  # RunHodl 0
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[3]',  # DevBurnt 1
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[8]/div[2]/div',  # top10% 2
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[4]/div/div[2]/div[3]/div[2]/div',  # insiders 3
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[6]/div[2]/div/div',  # rug probability 4
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[1]/div[1]/div[1]/div[2]/div[2]/div[1]/div/div',  # owner 5
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[3]/div[2]',  # liquidity 6
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[1]/div[1]/div/p', # name coin 7 / ЗАМЕНЕНО/
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[1]' # 8 age#1 - name, 2 - index на бирже, 3 - сокращенный контракт для чека(обычно чекают тот ли контракт по первым и последним символам)
    ]

    elements_texts = []

    for selector in selectors:
        elements = driver.find_elements(By.XPATH, selector)
        if elements:
            elements_texts.append(elements[0].text)
        else:
            elements_texts.append('undefined')


 # cto
    try:
        main_div = driver.find_element(By.XPATH,
                                       f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[1]')

        svgs = main_div.find_elements(By.TAG_NAME, 'svg')

        found_fill = False

        for svg in svgs:
            fill_value = svg.get_attribute('fill')
            if fill_value == '#FFD039':
                found_fill = True
                break

        elements_texts.append('true' if found_fill else 'false') # 9 cto
    except Exception:
        elements_texts.append('false')

    if elements_texts[1] == "Share":
        elements_texts[1] = "undefined"

    h24_div = ['2', '3', '4']

    for div_ in h24_div:
        try:
            h24 = driver.find_element(By.XPATH, f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[1]/div[4]')
            h24.click()
            break
        except Exception:
            continue

    try:
        ins_rug_div = driver.find_element(By.XPATH, f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div')
    except Exception:
        pass

    ins_rug_index = {"Insiders": 3, "Rug probability": 4}
    elements_texts[3] = 'undefined'
    elements_texts[4] = 'undefined'
    for key, index in ins_rug_index.items():
        try:
            # Ищем div, содержащий текстовое значение, например, 'Rug probability' или 'insiders'
            label_div = ins_rug_div.find_element(By.XPATH, f'.//div[contains(text(), "{key}")]')

            # Переходим к следующему div[2] от найденного элемента
            value_div = label_div.find_element(By.XPATH, './following-sibling::div[1]')

            # Получаем текст значения из div[2]
            value = value_div.text.strip()

            # Если значение найдено, записываем его в нужный индекс
            elements_texts[index] = value if value else "undefined"
        except Exception:
            # Если элемент не найден, оставляем значение "undefined"
            continue

    selectors_24h = [
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[3]/div[2]/div[2]/div',# LP Ratio  10
       # f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[3]/div[2]/div[2]/p',# initial liquidity
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[2]/div[4]/div[2]',# holders 11
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[2]/div[2]/div[2]',# Market cap 12
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[3]/div[2]/div[3]',# initial (в монете сети) 13#выводит в таком формате '365,39\n/17.5\n(+1.9K%)' из этого возьми только "17.5" 13
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[2]/div',# LP LOCK 14
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[1]/div[2]',# vol 15
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[2]/div[2]',# buy 16
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[3]/div[2]',# buy 17
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[4]/div[2]',# net 18
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[1]/div[1]', # 1st name 19
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[1]/div[2]', # 1st val 20
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[2]/div[1]', # 2nd name 21
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[2]/div[2]', # 2nd val 22
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[1]',  # 3rd name 23
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[2]',  # 3rd val 24
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[4]/div[1]',  # 4rd val 25
        f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[4]/div[2]/div',  # 4rd val 26
    ]

    for selector in selectors_24h:
        try:
            val = driver.find_element(By.XPATH, selector)
            if val:
                elements_texts.append(val.text)
        except Exception:
                elements_texts.append('undefined')

    if elements_texts[0] == '' and elements_texts[1] == 'undefined':
        socials_div = 2
    elif elements_texts[0] == '' and elements_texts[1] != 'undefined' or elements_texts[0] != '' and elements_texts[1] == '':
        socials_div = 3
    else:
        socials_div = 4

    link_owner_bool = False

    owner_divs = ['2', '3', '4', '5', '6', '7', '8']
    for owner_div in owner_divs:
        try:
            owner_element = driver.find_element(By.XPATH,
                                                f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{owner_div}]/div[2]/div[4]/div[3]/div[2]/a')
            link_owner = owner_element.get_attribute('href')

            if link_owner:
                link_owner_bool = True
            break
        except Exception:
            continue

    elements_texts.append(link_owner if link_owner_bool else 'undefined')
    try:
        selectors_link = driver.find_element(By.XPATH, f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[{socials_div}]/div')
    except Exception:
        pass

    elements_texts.append("twitter falsefalse") #twitter 28
    elements_texts.append("tg false") # tg 29
    elements_texts.append("web false") # website 30

    data_keys = {"twitter": 28, "telegram": 29, "website": 30}

    for key, index in data_keys.items():
        try:
            target_div = selectors_link.find_element(By.XPATH, f'.//div[@data-key="{key}"]')

            parent_div = target_div.find_element(By.XPATH, './..')

            link = parent_div.get_attribute('href')

            if link:
                elements_texts[index] = link
        except Exception:
            continue


    driver.quit()
    return elements_texts

