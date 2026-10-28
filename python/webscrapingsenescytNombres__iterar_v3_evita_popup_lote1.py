
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import io
import time
import os

def cerrar_popup(driver):
      """Cierra el popup jQuery UI Dialog de SENESCYT si está visible.
      No cambia de frame. Llámala en cualquier punto del loop."""
      try:
        dialogos = driver.find_elements(By.CSS_SELECTOR, "div.ui-dialog")
        if not any(d.is_displayed() for d in dialogos):
            return False
        print("⚠️  Popup detectado, cerrando...")
        driver.execute_script("""
              document.querySelectorAll('a.ui-dialog-titlebar-close').forEach(function(a) {
                  a.click();
              });
              document.querySelectorAll('.ui-dialog').forEach(function(d) {
                  d.style.setProperty('display', 'none', 'important');
              });
              document.querySelectorAll('.ui-widget-overlay').forEach(function(o) {
                  o.style.setProperty('display', 'none', 'important');
              });
          """)
        print("✅ Popup cerrado.")
        driver.execute_script("""
            var cleanupInterval = setInterval(function() {
                // Seleccionamos modales por clase y por etiquetas comunes de PrimeFaces/Bootstrap
                var elementsToRemove = document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], .ui-widget-overlay, .ui-dialog');
                
                if (elementsToRemove.length > 0) {
                    elementsToRemove.forEach(el => el.remove());
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = 'auto';
                    console.log("Popup eliminado dinámicamente");
                }
            }, 500);

            // Detener el intervalo tras 5 segundos para no consumir recursos innecesarios
            setTimeout(function() {
                clearInterval(cleanupInterval);
            }, 5000);
        """)


        return True
      except Exception as e:
          print(f"❌ Error al cerrar popup: {e}")
          return False

# Configura Tesseract
pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Cargar CSV con nombres completos
base_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_dir, 'nombres_completos.csv')
df = pd.read_csv(csv_path)
df['APELLIDOS'] = df['NOMBRE_COMPLETO'].str.split().str[:2].str.join(' ')

# Encabezados
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

# Resultados
all_rows = []
no_datos = []
no_info = []
contador_datos = 0

driver = webdriver.Chrome()
driver.get('https://www.senescyt.gob.ec/web/guest/consultas')
driver.maximize_window()
time.sleep(3)


# Inyectar un "limpiador" que se ejecute repetidamente por 5 segundos
driver.execute_script("""
    var cleanupInterval = setInterval(function() {
        // Seleccionamos modales por clase y por etiquetas comunes de PrimeFaces/Bootstrap
        var elementsToRemove = document.querySelectorAll('.modal, .modal-backdrop, [class*="modal"], .ui-widget-overlay, .ui-dialog');
        
        if (elementsToRemove.length > 0) {
            elementsToRemove.forEach(el => el.remove());
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';
            console.log("Popup eliminado dinámicamente");
        }
    }, 500);

    // Detener el intervalo tras 5 segundos para no consumir recursos innecesarios
    setTimeout(function() {
        clearInterval(cleanupInterval);
    }, 5000);
""")

print("🚀 Limpiador dinámico de popups activado.")
time.sleep(2) # Pausa mínima para que el JS actúe antes de buscar el iframe

# No hay iframe en la página, se omite el cambio de contexto
print("ℹ️ No se requiere cambiar a iframe.")

for i, row in df.iterrows():
    nombre_completo = row['NOMBRE_COMPLETO']
    apellidos = row['APELLIDOS']
    print(f"🔍 Buscando: {nombre_completo}")

    cerrar_popup(driver)
    # Leer captcha
    intentos, success = 0, False
    while intentos < 5 and not success:
        cerrar_popup(driver)
        campo = driver.find_element(By.ID, 'formPrincipal:apellidos')
        campo.clear()
        campo.send_keys(apellidos.strip())

        print(f"Intento {intentos + 1} para leer el CAPTCHA...")
        # Captura la imagen del CAPTCHA
        time.sleep(2)
        captcha_image = driver.find_element(By.ID, 'formPrincipal:capimg')
        captcha_location = captcha_image.location
        captcha_size = captcha_image.size
        captcha_image_screenshot = driver.get_screenshot_as_png()

        # Calcula las coordenadas para recortar la imagen del CAPTCHA
        left = captcha_location['x']
        top = captcha_location['y']
        right = captcha_location['x'] + captcha_size['width']
        bottom = captcha_location['y'] + captcha_size['height']

        # Recorta la imagen del CAPTCHA
        image = Image.open(io.BytesIO(captcha_image_screenshot))
        captcha_image = image.crop((left, top, right, bottom))

        # Mejora la calidad de la imagen
        captcha_image = captcha_image.convert('L')
        captcha_image = captcha_image.filter(ImageFilter.MedianFilter())
        enhancer = ImageEnhance.Contrast(captcha_image)
        captcha_image = enhancer.enhance(2)

        # Usa OCR para leer dígitos y letras del CAPTCHA
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        captcha_text = pytesseract.image_to_string(captcha_image, config=custom_config).strip()

        if len(captcha_text) == 4:
            try:
                # Ingresa el texto del CAPTCHA en el campo correcto
                captcha_field = driver.find_element(By.ID, 'formPrincipal:captchaSellerInput')
                captcha_field.clear()
                captcha_field.send_keys(captcha_text)

                # Clic en el botón de enviar
                driver.find_element(By.ID, 'formPrincipal:boton-buscar').click()
                time.sleep(4)
                cerrar_popup(driver)


                # Reparsear página con BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                mensaje_error = soup.find("div", class_="msg-rojo")
                if mensaje_error and "no se obtuvieron resultado" in mensaje_error.text.lower():
                    print(f"❌ No se encontraron resultados para {apellidos}")
                    no_info.append(nombre_completo)
                    break  # sale del while, sin éxito



                # Buscar el panel de Informaciónresultados de la busqueda
                panel_info = soup.find("div", id="formPrincipal:tablaTitulado")


                # Verificar si contiene una tabla con resultados de la busqueda
                success = False
                if panel_info and panel_info.find("table"):
                    success = True
                    print("✅ Panel de Información coincidencias de apellido con tabla.")
                else:
                    print("❌ Panel de Información coincidencias de apellido con tabla no encontrado.")

            except Exception as e:
                print(f"❌ Error en el proceso: {e}")
        else:
            driver.find_element(By.ID, 'formPrincipal:boton-buscar').click()
            cerrar_popup(driver)
            time.sleep(3)

        # Intento fallido, hacer clic en "Buscar" para recargar el CAPTCHA
        if not success:
            print("🔄 CAPTCHA incorrecto, recargando e ingresando ID nuevamente...")
            try:
                submit_button = driver.find_element(By.ID, 'formPrincipal:boton-buscar')
                ActionChains(driver).move_to_element(submit_button).click().perform()
                time.sleep(2)
            except Exception as e:
                print(f"❌ No se pudo recargar el CAPTCHA ni reingresar ID: {e}")

        intentos += 1
        print(success)
        cerrar_popup(driver)

    if not success:
        print("❌ No se pudo resolver el CAPTCHA")
        no_datos.append(nombre_completo)
        continue

    try:
        tabla_resultados = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'formPrincipal:tablaTitulado_data'))
        )
        filas = tabla_resultados.find_elements(By.TAG_NAME, "tr")
        match_encontrado = False

        cerrar_popup(driver)

        for fila in filas:
            cerrar_popup(driver)
            columnas = fila.find_elements(By.TAG_NAME, "td")
            if len(columnas) >= 3:
                texto_nombre = columnas[1].text.strip()
                if texto_nombre.upper() == nombre_completo.upper():
                    boton = columnas[2].find_element(By.LINK_TEXT, "Ver Información")
                    ActionChains(driver).move_to_element(boton).click().perform()
                    match_encontrado = True

                    ####
                    # Esperar carga de página individual
                    time.sleep(3)
                    soup = BeautifulSoup(driver.page_source, 'html.parser')

                    # Obtener identificación e info personal
                    identificacion = None
                    tablas = soup.find_all("table")
                    for row_html in tablas[2].find_all('tr'):
                        cols = row_html.find_all('td')
                        if len(cols) == 2 and "Identificación" in cols[0].text:
                            identificacion = cols[1].text.strip()
                            break

                    if not identificacion:
                        no_datos.append(nombre_completo)
                        print("⚠️ No se encontró identificación para:", nombre_completo)
                        continue

                    info_personal = [None, None, None]
                    for row_html in tablas[2].find_all('tr'):
                        cols = row_html.find_all('td')
                        if len(cols) == 2:
                            key = cols[0].text.strip()
                            val = cols[1].text.strip()
                            if "Nombres" in key: info_personal[0] = val
                            elif "Género" in key: info_personal[1] = val
                            elif "Nacionalidad" in key: info_personal[2] = val

                    paneles = soup.find_all("div", class_="panel panel-primary")
                    rows = []
                    for panel in paneles:
                        titulo = panel.find("h4", class_="panel-title")
                        titulo_tabla = titulo.text.strip() if titulo else "Sin título"
                        tabla = panel.find("table")
                        if not tabla:
                            continue
                        for fila_html in tabla.find_all('tr'):
                            cols = fila_html.find_all('td')
                            if not cols: continue
                            celdas = []
                            for col in cols:
                                span = col.find('span')
                                if span: span.extract()
                                celdas.append(col.text.strip() if col.text.strip() else None)
                            if len(celdas) == 8:
                                fila_completa = [identificacion] + info_personal + celdas + [titulo_tabla]
                                rows.append(fila_completa)

                    if rows:
                        all_rows.extend(rows)
                        contador_datos += 1
                        print(f"✅ {len(rows)} filas añadidas para {nombre_completo}")
                        if contador_datos % 10 == 0:
                            pd.DataFrame(all_rows, columns=headers).to_csv(f"{base_dir}/resultados_{contador_datos}.csv", index=False)
                    else:
                        no_datos.append(nombre_completo)
                    cerrar_popup(driver)




                    #break
        if not match_encontrado:
            print(f"⚠️ No se encontró coincidencia exacta en tabla para: {nombre_completo}")
            no_info.append(nombre_completo)
            continue
    except Exception as e:
        print(f"❌ Error al procesar tabla de resultados: {e}")
        no_datos.append(nombre_completo)
        continue
    cerrar_popup(driver)




# Guardar resultados finales
pd.DataFrame(all_rows, columns=headers).to_csv(os.path.join(base_dir, 'senescyt_titulos_por_apellido.csv'), index=False)
pd.DataFrame(no_datos, columns=['NOMBRE_COMPLETO']).to_csv(os.path.join(base_dir, 'no_encontrados_apellidos.csv'), index=False)
pd.DataFrame(no_info, columns=['NOMBRE_COMPLETO']).to_csv(os.path.join(base_dir, 'no_info_apellidos.csv'), index=False)

driver.quit()
print("🟢 Proceso finalizado.")
