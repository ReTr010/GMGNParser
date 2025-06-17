from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio


async def parse_component(chain, address):
    async with async_playwright() as p:
        # Настройка браузера
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        )

        page = await context.new_page()

        if chain.lower() == 'ethereum':
            chain = "eth"
        if chain.lower() == 'solana':
            chain = "sol"

        # Формируем ссылку
        url = f'https://gmgn.ai/{chain}/token/{address}'
        await page.goto(url)

        try:
            # Ожидаем и закрываем JS окно
            close_button = await page.wait_for_selector('xpath=/html/body/div[5]/div[3]/div/section/button',
                                                        timeout=10000)
            await close_button.click()
        except PlaywrightTimeoutError:
            print("Ошибка при нажатии на крестик или окно не появилось")

        # Проверка на ошибки
        has_error = False
        try:
            error_div = page.locator('//*[@id="__next"]/div/div/main/div[2]')
            error_div_text = await error_div.text_content()

            error_texts = [
                "This token has very low liquidity. Be careful when trading!",
                "Might be Honeypot!! Token Frozen blacklist enabled."
            ]
            has_error = any(error_text in error_div_text for error_text in error_texts)
            print("Ошибки найдены:", has_error)
        except:
            print("Элемент main/div[2] не найден")

        error_div = 3 if has_error else 2

        # Определение селекторов
        selectors = [
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[2]',
            # RunHodl 0
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[3]',
            # DevBurnt 1
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[8]/div[2]/div',  # top10% 2
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[4]/div/div[2]/div[3]/div[2]/div',
            # insiders 3
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[6]/div[2]/div/div',
            # rug probability 4
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[1]/div[1]/div[1]/div[2]/div[2]/div[1]/div/div',
            # owner 5
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[2]/div[3]/div[2]',  # liquidity 6
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[1]/div[1]/div/p',
            # name coin 7
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[1]'  # age 8
        ]

        elements_texts = []

        # Получение текста элементов
        for selector in selectors:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    elements_texts.append(await element.first.text_content())
                else:
                    elements_texts.append('undefined')
            except:
                elements_texts.append('undefined')

        # Проверка CTO
        try:
            main_div = page.locator(
                f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[1]')
            svgs = await main_div.locator('svg').all()

            found_fill = False
            for svg in svgs:
                fill_value = await svg.get_attribute('fill')
                if fill_value == '#FFD039':
                    found_fill = True
                    break

            elements_texts.append('true' if found_fill else 'false')  # 9 cto
        except:
            elements_texts.append('false')

        if elements_texts[1] == "Share":
            elements_texts[1] = "undefined"

        # Обработка h24
        h24_div = ['2', '3', '4']
        div_ = None

        for div_num in h24_div:
            try:
                h24_selector = f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_num}]/div/div[1]/div[4]'
                h24 = page.locator(h24_selector)
                if await h24.count() > 0:
                    await h24.click()
                    div_ = div_num
                    break
            except:
                continue

        # Добавляем небольшую задержку после клика
        await asyncio.sleep(1)

        # Обработка ins_rug
        try:
            ins_rug_div = page.locator(
                f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div')
        except:
            pass

        ins_rug_index = {"Insiders": 3, "Rug probability": 4}
        elements_texts[3] = 'undefined'
        elements_texts[4] = 'undefined'

        for key, index in ins_rug_index.items():
            try:
                label = ins_rug_div.locator(f'text={key}')
                if await label.count() > 0:
                    value_div = label.locator('xpath=./following-sibling::div[1]')
                    value = await value_div.text_content()
                    elements_texts[index] = value.strip() if value else "undefined"
            except:
                continue

        # Селекторы для 24h данных
        selectors_24h = [
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[3]/div[2]/div[2]/div',
            # LP Ratio 10
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[2]/div[4]/div[2]',
            # holders 11
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[2]/div[2]/div[2]',
            # Market cap 12
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[3]/div[2]/div[3]',
            # initial 13
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[2]/div',
            # LP LOCK 14
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[1]/div[2]',
            # vol 15
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[2]/div[2]',
            # buy 16
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[3]/div[2]',
            # sell 17
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[1]/div[1]/div[4]/div[2]',
            # net 18
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[1]/div[1]',
            # 1st name 19
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[1]/div[2]',
            # 1st val 20
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[2]/div[1]',
            # 2nd name 21
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[2]/div[2]',
            # 2nd val 22
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[1]',
            # 3rd name 23
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[3]/div[2]',
            # 3rd val 24
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[4]/div[1]',
            # 4th name 25
            f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{div_}]/div/div[2]/div[2]/div[4]/div[2]/div',
            # 4th val 26
        ]

        for selector in selectors_24h:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    elements_texts.append(await element.text_content())
                else:
                    elements_texts.append('undefined')
            except:
                elements_texts.append('undefined')

        # Определение socials_div
        if elements_texts[0] == '' and elements_texts[1] == 'undefined':
            socials_div = 2
        elif (elements_texts[0] == '' and elements_texts[1] != 'undefined') or (
                elements_texts[0] != '' and elements_texts[1] == ''):
            socials_div = 3
        else:
            socials_div = 4

        # Проверка owner link
        link_owner = 'undefined'
        for owner_div in ['2', '3', '4', '5', '6', '7', '8']:
            try:
                owner_selector = f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[2]/div[2]/div[{owner_div}]/div[2]/div[4]/div[3]/div[2]/a'
                owner_element = page.locator(owner_selector)
                if await owner_element.count() > 0:
                    link_owner = await owner_element.get_attribute('href')
                    break
            except:
                continue

        elements_texts.append(link_owner if link_owner != 'undefined' else 'undefined')

        # Социальные ссылки
        try:
            selectors_link = page.locator(
                f'//*[@id="__next"]/div/div/main/div[{error_div}]/div[2]/div[1]/div[1]/div/div[3]/div[2]/div[{socials_div}]/div')
        except:
            pass

        elements_texts.append("twitter falsefalse")  # twitter 28
        elements_texts.append("tg false")  # tg 29
        elements_texts.append("web false")  # website 30

        data_keys = {"twitter": 28, "telegram": 29, "website": 30}

        for key, index in data_keys.items():
            try:
                target_div = selectors_link.locator(f'div[data-key="{key}"]')
                if await target_div.count() > 0:
                    parent = target_div.locator('xpath=./..')
                    link = await parent.get_attribute('href')
                    if link:
                        elements_texts[index] = link
            except:
                continue

        await browser.close()
        return elements_texts

# # # Пример использования
# async def main():
#     result = await parse_component('sol', '4yCuUMPFvaqxK71CK6SZc3wmtC2PDpDN9mcBzUkepump')
#     for i, value in enumerate(result):
#         print(f'{i} = {value}')
#
# if __name__ == "__main__":
#     asyncio.run(main())
