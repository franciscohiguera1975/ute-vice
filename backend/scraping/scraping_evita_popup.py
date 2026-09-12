import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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
        return True
      except Exception as e:
          print(f"❌ Error al cerrar popup: {e}")
          return False

# Obtén la ruta absoluta de la carpeta donde se encuentra este script
# Verificar como sale 1720482015
base_dir = os.path.dirname(os.path.abspath(__file__))

# Construye la ruta relativa al archivo CSV
csv_path = os.path.join(base_dir, 'identificaciones_no_encontradas.csv')

# Configura la ruta de Tesseract
pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Leer el archivo CSV
identificaciones = pd.read_csv(csv_path, sep=',')
ids = identificaciones['IDENTIFICACION'].tolist()

# Definimos los headers, añadiendo Información Personal
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
    'Título de Tabla'  # 🆕 Nueva columna
]

# Lista para acumular todas las filas de datos
all_rows = []

# Lista para acumular las identificaciones que no encontraron datos
no_datos = []
no_info = []
# Contador para guardar cada 2 registros encontrados
contador_datos = 0

# Configura el navegador
driver = webdriver.Chrome()
# Cargar la página
driver.get('https://www.senescyt.gob.ec/web/guest/consultas')
driver.maximize_window()

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




# Cambia al iframe si es necesario
try:
    iframe = driver.find_element(By.TAG_NAME, 'iframe')
    driver.switch_to.frame(iframe)
except Exception as e:
    print(f"No se encontró el iframe: {e}")

# Iterar sobre cada identificación
nId = 0
for identificacion in ids:
    print(f"Procesando identificación: {identificacion}")
    cerrar_popup(driver)


    # 🔄 **Intentos para el CAPTCHA**
    max_intentos = 5
    intentos = 0
    captcha_text = ""
    success = False

    while intentos < max_intentos and not success:
        cerrar_popup(driver)
        # Ingresa el número de identificación
        id_field = driver.find_element(By.ID, 'formPrincipal:identificacion')
        id_field.clear()
        id_field.send_keys(str(identificacion))

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
                submit_button = driver.find_element(By.ID, 'formPrincipal:boton-buscar')
                ActionChains(driver).move_to_element(submit_button).click().perform()

                # Espera un momento para validar si cargó correctamente
                time.sleep(5)

                # Reparsear página con BeautifulSoup
                soup = BeautifulSoup(driver.page_source, 'html.parser')

                mensaje_error = soup.find("div", class_="msg-rojo")
                if mensaje_error and "no se obtuvieron resultado" in mensaje_error.text.lower():
                    print(f"❌ No se encontraron resultados para ID {identificacion}")
                    no_info.append(identificacion)
                    break  # sale del while, sin éxito

                # Buscar el panel de Información Personal por su ID específico
                panel_info = soup.find("div", id="formPrincipal:pnlInfoPersonal")

                # Verificar si contiene una tabla
                success = False
                if panel_info and panel_info.find("table"):
                    success = True
                    print("✅ Panel de Información Personal detectado con tabla.")
                else:
                    print("❌ Panel de Información Personal no encontrado o sin tabla.")


            except Exception as e:
                print(f"❌ Error en el proceso: {e}")
        
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

    if not success:
        print(f"No se pudo completar la consulta para ID {identificacion}. Agregando a la lista de no encontrados.")
        no_datos.append(identificacion)
        continue


    # 🔄 Esperar y actualizar el contenido de la página
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    rows = []  # Reiniciar filas por identificación

    # Extraer información personal (tabla 3)
    info_personal = [None, None, None]
    tables = soup.find_all('table')
    if len(tables) > 3:
        info_rows = tables[2].find_all('tr')
        for row in info_rows:
            cols = row.find_all('td')
            if len(cols) == 2:
                key = cols[0].text.strip()
                val = cols[1].text.strip()
                if "Nombres" in key:
                    info_personal[0] = val
                elif "Género" in key:
                    info_personal[1] = val
                elif "Nacionalidad" in key:
                    info_personal[2] = val

    # Buscar todos los paneles que contengan título y tabla
    paneles = soup.find_all("div", class_="panel panel-primary")

    for panel in paneles:
        # Extraer título del panel
        titulo_element = panel.find("h4", class_="panel-title")
        titulo_tabla = titulo_element.text.strip() if titulo_element else "Sin título"

        # Buscar tabla dentro del panel
        tabla = panel.find("table")
        if not tabla:
            continue

        # Extraer filas de datos
        for fila_html in tabla.find_all('tr'):
            columnas = fila_html.find_all('td')
            if not columnas:
                continue  # Saltar encabezados o filas vacías

            celdas = []
            for col in columnas:
                span = col.find('span')
                if span:
                    span.extract()
                texto = col.get_text(strip=True)
                celdas.append(texto if texto else None)

            # Verificamos que la fila tenga el número correcto de celdas (de datos)
            if len(celdas) == 8:
                fila_completa = [identificacion] + info_personal + celdas + [titulo_tabla]
                rows.append(fila_completa)

    # Si hay filas válidas, las añadimos
    if rows:
        all_rows.extend(rows)
        contador_datos += 1
        print(f"✅ {len(rows)} filas añadidas para ID {identificacion}")

        if contador_datos % 10 == 0:
            temp_df = pd.DataFrame(all_rows, columns=headers)
            temp_path = os.path.join(base_dir, f'resultados_{contador_datos}.csv')
            temp_df.to_csv(temp_path, index=False, encoding='utf-8')
            print(f"💾 Guardado temporal en: {temp_path}")
    else:
        no_datos.append(identificacion)
        print(f"⚠️ No se encontraron filas válidas para {identificacion}")
    nId += 1

    cerrar_popup(driver)
    print(f"Identificacion Nro {nId} : {identificacion}")


# Crear un único DataFrame con toda la información
df_final = pd.DataFrame(all_rows, columns=headers)

# Crear un DataFrame con las identificaciones que no encontraron datos
df_no_datos = pd.DataFrame(no_datos, columns=['Identificación'])
df_no_info = pd.DataFrame(no_info, columns=['Identificación'])

# Mostrar las primeras filas del DataFrame consolidado
print(df_final.head())

# Guardar en un CSV (opcional, si lo quieres exportar)
# Construye la ruta relativa para guardar el archivo
output_path = os.path.join(base_dir, 'senescyt_titulos.csv')
no_datos_path = os.path.join(base_dir, 'identificaciones_no_encontradas.csv')
no_info_path = os.path.join(base_dir, 'identificaciones_no_info.csv')

df_final.to_csv(output_path, index=False, encoding='utf-8')
df_no_datos.to_csv(no_datos_path, index=False, encoding='utf-8')
df_no_info.to_csv(no_info_path, index=False, encoding='utf-8')

print(f"Datos guardados en: {output_path}")
print(f"Identificaciones sin datos guardadas en: {no_datos_path}")                                                                                                       
# Cierra el navegador
driver.quit()
