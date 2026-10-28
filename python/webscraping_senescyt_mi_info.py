import io
import logging
import os
import shutil
import time

import pandas as pd
import pytesseract
from bs4 import BeautifulSoup
from PIL import Image, ImageEnhance, ImageFilter
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By


# ---------------------------
# Configuración de Ubuntu
# ---------------------------
def find_tesseract_binary():
    candidates = [
        shutil.which("tesseract"),
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "No se encontró Tesseract. Instálalo con: sudo apt-get update && sudo apt-get install -y tesseract-ocr"
    )


def find_chrome_binary():
    candidates = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/opt/google/chrome/google-chrome",
        "/snap/bin/chromium",
        shutil.which("chromium-browser"),
        shutil.which("chromium"),
        shutil.which("google-chrome-stable"),
        shutil.which("google-chrome"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "No se encontró Chrome/Chromium. Instálalo con: sudo apt-get install -y chromium chromium-driver"
    )


def find_chromedriver_binary():
    candidates = [
        shutil.which("chromedriver"),
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise RuntimeError(
        "No se encontró chromedriver. Instálalo con: sudo apt-get install -y chromium-driver"
    )


# ---------------------------
# Variables con tu información
# ---------------------------
CI = "1717670960"
# Cuántas veces refrescar y releer el CAPTCHA antes de desistir. La búsqueda es
# siempre por cédula: nunca se cae a buscar por apellidos.
MAX_CAPTCHA_RETRIES = 30
NOMBRES = "Cristian Guillermo"
APELLIDOS = "Rivadeneira Cedeño"
NOMBRE_COMPLETO = f"{NOMBRES} {APELLIDOS}".strip()

# Si quieres guardar en CSV con la estructura que usa el script principal.
# key exacto: NOMBRE_COMPLETO
# (y puedes agregar CI como columna si quieres)

df = pd.DataFrame([
    {
        "CI": CI,
        "NOMBRE_COMPLETO": NOMBRE_COMPLETO,
        "NOMBRES": NOMBRES,
        "APELLIDOS": APELLIDOS,
    }
])

# Para este caso, la búsqueda por apellidos debe usar exactamente tus apellidos,
# no recortar el nombre completo como si fueran apellidos.
df["APELLIDOS"] = df["APELLIDOS"].astype(str)

headers = [
    'Identificación',
    'Nombres',
    'Género',
    'Nacionalidad',
    'Título',
    'Institución de Educación Superior',
    'Tipo',
    'Reconocido Por',
    'Número de Registro',
    'Fecha de Registro',
    'Área o Campo de Conocimiento',
    'Observación',
    'Título de Tabla'
]

all_rows = []
no_datos = []
no_info = []


# ---------------------------
# Utilidades
# ---------------------------
def normalize_name(value):
    if value is None:
        return ''
    value = str(value).upper()
    value = value.replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
    value = value.replace('Ñ', 'N')
    value = ''.join(ch for ch in value if ch.isalnum() or ch.isspace())
    return ' '.join(value.split())


def set_identificacion_value(driver, value):
    ids = [
        'formPrincipal:identificacion',
    ]
    for element_id in ids:
        try:
            campo = driver.find_element(By.ID, element_id)
            campo.clear()
            campo.send_keys(value)
            return True
        except Exception:
            pass
    return False


def row_name_matches(row_text):
    text = normalize_name(row_text)
    full = normalize_name(NOMBRE_COMPLETO)
    last = normalize_name(APELLIDOS)
    first = normalize_name(NOMBRES)
    first_only = normalize_name(NOMBRES.split()[0])
    return (
        full in text
        or (first in text and last in text)
        or (first_only in text and last in text)
    )


def cerrar_popup(driver):
    try:
        dialogos = driver.find_elements(By.CSS_SELECTOR, "div.ui-dialog")
        if not any(d.is_displayed() for d in dialogos):
            return False
        print("⚠️ Popup detectado, cerrando...")
        driver.execute_script("""
            document.querySelectorAll('a.ui-dialog-titlebar-close').forEach(function(a) { a.click(); });
            document.querySelectorAll('.ui-dialog').forEach(function(d) { d.style.setProperty('display', 'none', 'important'); });
            document.querySelectorAll('.ui-widget-overlay').forEach(function(o) { o.style.setProperty('display', 'none', 'important'); });
        """)
        driver.execute_script("""
            var cleanupInterval = setInterval(function() {
                var elementsToRemove = document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], .ui-widget-overlay, .ui-dialog');
                if (elementsToRemove.length > 0) {
                    elementsToRemove.forEach(el => el.remove());
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = 'auto';
                }
            }, 500);
            setTimeout(function() { clearInterval(cleanupInterval); }, 5000);
        """)
        return True
    except Exception as exc:
        print(f"❌ Error al cerrar popup: {exc}")
        return False


# ---------------------------
# Arrancar Selenium
# ---------------------------
# El chromium del sistema reenvía al snap, cuyo confinamiento a veces impide
# que Selenium le mande SIGTERM al cerrar; es inofensivo, solo se silencia el ruido.
logging.getLogger('selenium.webdriver.common.service').setLevel(logging.CRITICAL)

pytesseract.pytesseract_cmd = find_tesseract_binary()

chrome_options = Options()
chrome_options.binary_location = find_chrome_binary()
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--window-size=1600,1200')
chrome_options.add_argument('--start-maximized')
chrome_options.add_argument('--headless=new')

service = Service(executable_path=find_chromedriver_binary())
driver = webdriver.Chrome(service=service, options=chrome_options)

base_dir = os.path.dirname(os.path.abspath(__file__))

try:
    driver.get('https://www.senescyt.gob.ec/web/guest/consultas')
    time.sleep(3)

    driver.execute_script("""
        var cleanupInterval = setInterval(function() {
            var elementsToRemove = document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], .ui-widget-overlay, .ui-dialog');
            if (elementsToRemove.length > 0) {
                elementsToRemove.forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = 'auto';
            }
        }, 500);
        setTimeout(function() { clearInterval(cleanupInterval); }, 5000);
    """)

    print(f"🔍 Buscando persona: {NOMBRE_COMPLETO}")
    print(f"📌 CI: {CI}")

    found_result = False

    try:
        cerrar_popup(driver)
        if not set_identificacion_value(driver, CI):
            print(f"⚠️ No pude ubicar el campo de identificación para la cédula {CI}")
        time.sleep(2)

        captcha_text = ''
        for captcha_intento in range(1, MAX_CAPTCHA_RETRIES + 1):
            # El campo de identificación puede perder el valor al refrescar el
            # CAPTCHA (postback de JSF), así que se vuelve a escribir en cada vuelta.
            set_identificacion_value(driver, CI)

            captcha_image = driver.find_element(By.ID, 'formPrincipal:capimg')
            captcha_location = captcha_image.location
            captcha_size = captcha_image.size
            screenshot = driver.get_screenshot_as_png()

            left = captcha_location['x']
            top = captcha_location['y']
            right = captcha_location['x'] + captcha_size['width']
            bottom = captcha_location['y'] + captcha_size['height']

            image = Image.open(io.BytesIO(screenshot)).crop((left, top, right, bottom))
            image = image.convert('L')
            image = image.filter(ImageFilter.MedianFilter())
            image = ImageEnhance.Contrast(image).enhance(2)

            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
            captcha_text = pytesseract.image_to_string(image, config=custom_config).strip()

            if len(captcha_text) != 4:
                print(f"🔁 CAPTCHA ilegible ('{captcha_text}'), refrescando ({captcha_intento}/{MAX_CAPTCHA_RETRIES})...")
                try:
                    driver.find_element(By.ID, 'formPrincipal:boton-buscar').click()
                    cerrar_popup(driver)
                    time.sleep(2)
                except Exception:
                    pass
                continue

            try:
                captcha_field = driver.find_element(By.ID, 'formPrincipal:captchaSellerInput')
                captcha_field.clear()
                captcha_field.send_keys(captcha_text)
                driver.find_element(By.ID, 'formPrincipal:boton-buscar').click()
                time.sleep(4)
                cerrar_popup(driver)

                soup = BeautifulSoup(driver.page_source, 'html.parser')

                mensaje_error = soup.find('div', class_='msg-rojo')
                if mensaje_error and 'no se obtuvieron resultado' in mensaje_error.text.strip().lower():
                    print(f"❌ No se encontraron resultados para la cédula {CI}")
                    break

                captcha_incorrecto = soup.find(class_='ui-messages-error-detail')
                if captcha_incorrecto:
                    print(f"🔁 CAPTCHA rechazado por el portal ('{captcha_incorrecto.text.strip()}'), reintentando ({captcha_intento}/{MAX_CAPTCHA_RETRIES})...")
                    continue

                # Al buscar por cédula el portal va directo a la ficha personal,
                # sin lista intermedia ni botón "Ver Información".
                panel_info_personal = soup.find('div', id='formPrincipal:pnlInfoPersonal')
                if not panel_info_personal:
                    print(f"🔁 Ficha personal no encontrada todavía, reintentando ({captcha_intento}/{MAX_CAPTCHA_RETRIES})...")
                    continue

                identificacion = None
                info_personal = [None, None, None]
                for row_html in panel_info_personal.find_all('tr'):
                    cols = row_html.find_all('td')
                    if len(cols) != 2:
                        continue
                    key = cols[0].text.strip()
                    val = cols[1].text.strip()
                    if 'Identificación' in key:
                        identificacion = val
                    elif 'Nombres' in key:
                        info_personal[0] = val
                    elif 'Género' in key:
                        info_personal[1] = val
                    elif 'Nacionalidad' in key:
                        info_personal[2] = val

                if not identificacion:
                    print('⚠️ No se encontró identificación en la ficha personal.')
                    break

                if not row_name_matches(info_personal[0] or ''):
                    print(f"⚠️ La ficha encontrada no coincide con el nombre esperado: {info_personal[0]!r}")

                found_result = True
                paneles = soup.find_all('div', class_='panel panel-primary')
                for panel in paneles:
                    if panel.get('id') == 'formPrincipal:pnlInfoPersonal':
                        continue
                    titulo = panel.find('h4', class_='panel-title')
                    titulo_tabla = titulo.text.strip() if titulo else 'Sin título'
                    tabla = panel.find('table')
                    if not tabla:
                        continue
                    for fila_html in tabla.find_all('tr'):
                        cols = fila_html.find_all('td')
                        if not cols:
                            continue
                        celdas = []
                        for col in cols:
                            span = col.find('span')
                            if span:
                                span.extract()
                            celdas.append(col.text.strip() if col.text.strip() else None)
                        if len(celdas) == 8:
                            fila_completa = [identificacion] + info_personal + celdas + [titulo_tabla]
                            all_rows.append(fila_completa)

                print(f"✅ Registro encontrado y guardado para: {NOMBRE_COMPLETO} ({len(all_rows)} título(s))")

            except Exception as exc:
                print(f"❌ Error en el proceso de búsqueda: {exc}")

            break

    except Exception as exc:
        print(f"❌ Error global durante la búsqueda por cédula: {exc}")

    if not found_result:
        print(f"⚠️ No se encontró coincidencia exacta para: {NOMBRE_COMPLETO}")
        no_info.append(NOMBRE_COMPLETO)

    result_path = os.path.join(base_dir, 'resultado_mi_senescyt.csv')
    pd.DataFrame(all_rows, columns=headers).to_csv(result_path, index=False)
    pd.DataFrame(no_datos, columns=['NOMBRE_COMPLETO']).to_csv(
        os.path.join(base_dir, 'no_encontrados_mi_senescyt.csv'),
        index=False,
    )
    pd.DataFrame(no_info, columns=['NOMBRE_COMPLETO']).to_csv(
        os.path.join(base_dir, 'no_info_mi_senescyt.csv'),
        index=False,
    )

    print(f"📄 Resultado guardado en: {result_path}")

finally:
    try:
        driver.quit()
    except Exception:
        pass
    print('🟢 Proceso finalizado.')
