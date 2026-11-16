#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMOTIONLAB | Conversión de mensaje del equipo a archivo JSON válido
==================================================================

Origen de los datos
-------------------
El equipo de EmotionLab compartió un mensaje de texto con registros que,
según lo informado, fueron extraídos del almacenamiento de AWS (S3).
El contenido se entregó como texto pegado: los objetos de las sesiones
estaban presentes, pero el mensaje incluía una frase introductoria y
un cierre que impedían interpretarlo directamente como JSON.

Objetivo de este script
-----------------------
1. Leer ese mensaje desde un archivo .txt local.
2. Corregir ÚNICAMENTE la estructura externa para obtener una lista JSON.
3. Validar que cada sesión y su lista de respuestas tengan una estructura
   interpretable, sin modificar respuestas, puntuaciones ni identificadores.
4. Guardar el resultado en un archivo .json con codificación UTF-8.

Este script NO accede a AWS, NO entrena el modelo y NO imputa valores.
La corrección especial solo se aplica al formato de mensaje identificado;
si llega otro formato desconocido, el programa informa el problema en lugar
de intentar adivinar datos.

Requisitos: Python 3.9 o superior; solo biblioteca estándar.

Uso en VS Code (colocar el .txt junto a este archivo):
    python convertir_mensaje_aws_a_json_emotionlab.py

Opcionalmente, indicar otros archivos:
    python convertir_mensaje_aws_a_json_emotionlab.py --entrada "mensaje.txt" --salida "salida.json"
"""

import argparse
import json
import re
from pathlib import Path


ENCABEZADO_DEL_MENSAJE = "json real con tus respuestas"
NOMBRE_ENTRADA = "Texto pegado(6).txt"
NOMBRE_SALIDA = "emotionlab_unity_7_sesiones.json"


def interpretar_mensaje(texto: str) -> list[dict]:
    """Convierte un JSON válido o el formato concreto del mensaje del equipo.

    Nunca se cambian los valores de los objetos: solo su envoltura externa.
    """
    contenido = texto.lstrip("\ufeff").strip()

    try:
        # Primera opción: el texto ya es un JSON válido.
        estructura = json.loads(contenido)
    except json.JSONDecodeError as error_original:
        # Segunda opción: reconocemos SOLO la envoltura del mensaje recibido.
        # Ejemplo original:
        #   json real con tus respuestas {sesión 1}, {sesión 2}, ... ] }
        if not contenido.casefold().startswith(ENCABEZADO_DEL_MENSAJE):
            raise ValueError(
                "El texto no es JSON válido y su encabezado no corresponde "
                "al formato del mensaje de EmotionLab conocido. "
                f"Detalle: {error_original}"
            ) from error_original

        cuerpo = contenido[len(ENCABEZADO_DEL_MENSAJE):].strip()
        cierre = re.search(r"\]\s*\}\s*$", cuerpo)
        if cierre is None:
            raise ValueError(
                "No se encontró el cierre esperado '] }' del mensaje. "
                "No se realizarán reparaciones automáticas desconocidas."
            ) from error_original

        # Los registros completos ya están separados por comas.
        # Solo reconstruimos los corchetes de la lista externa.
        objetos = cuerpo[:cierre.start()].strip()
        try:
            estructura = json.loads("[\n" + objetos + "\n]")
        except json.JSONDecodeError as error:
            raise ValueError(
                "El contenido de las sesiones no se pudo interpretar. "
                f"No se han modificado los datos. Detalle: {error}"
            ) from error

    # Se admiten tres presentaciones de datos, sin alterar los registros.
    if isinstance(estructura, list):
        sesiones = estructura
    elif isinstance(estructura, dict) and isinstance(
        estructura.get("registros"), list
    ):
        sesiones = estructura["registros"]
    elif isinstance(estructura, dict) and isinstance(
        estructura.get("sesiones"), list
    ):
        sesiones = estructura["sesiones"]
    elif isinstance(estructura, dict) and "session_data" in estructura:
        sesiones = [estructura]
    else:
        raise ValueError(
            "Formato JSON válido, pero sin una lista de sesiones reconocible."
        )

    if not sesiones:
        raise ValueError("No hay sesiones para exportar.")

    for indice, registro in enumerate(sesiones, start=1):
        if not isinstance(registro, dict):
            raise ValueError(f"La sesión {indice} no es un objeto JSON.")
        sesion = registro.get("session_data", registro)
        if not isinstance(sesion, dict):
            raise ValueError(f"La sesión {indice} no contiene datos válidos.")
        if not isinstance(sesion.get("respuestas", []), list):
            raise ValueError(f"La sesión {indice} tiene 'respuestas' inválidas.")

    return sesiones


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convierte un mensaje del equipo de EmotionLab a JSON válido."
    )
    parser.add_argument(
        "--entrada", default=NOMBRE_ENTRADA,
        help="Archivo .txt recibido del equipo (por defecto: Texto pegado(6).txt)."
    )
    parser.add_argument(
        "--salida", default=NOMBRE_SALIDA,
        help="Archivo .json que se generará."
    )
    opciones = parser.parse_args()

    # Por defecto, buscamos el TXT junto a este script (funciona en VS Code
    # aunque el directorio de trabajo del terminal sea diferente).
    directorio_script = Path(__file__).resolve().parent
    entrada = Path(opciones.entrada).expanduser()
    if not entrada.is_absolute():
        entrada = directorio_script / entrada

    salida = Path(opciones.salida).expanduser()
    if not salida.is_absolute():
        salida = directorio_script / salida

    if not entrada.is_file():
        parser.error(
            f"No se encontró el archivo de origen: {entrada}\n"
            "Coloca el mensaje .txt en la misma carpeta que este script "
            "o utiliza --entrada."
        )

    if entrada.resolve() == salida.resolve():
        parser.error("La salida no puede sobrescribir el mensaje original.")

    try:
        texto_original = entrada.read_text(encoding="utf-8-sig")
        sesiones = interpretar_mensaje(texto_original)

        # Validación explícita antes de guardar.
        json_resultante = json.dumps(sesiones, ensure_ascii=False, indent=2)
        if json.loads(json_resultante) != sesiones:
            raise ValueError("La verificación de contenido no coincidió.")

        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(json_resultante + "\n", encoding="utf-8")

        total_respuestas = sum(
            len(registro.get("session_data", registro).get("respuestas", []))
            for registro in sesiones
        )
        con_respuestas = sum(
            bool(registro.get("session_data", registro).get("respuestas", []))
            for registro in sesiones
        )

        print("EMOTIONLAB | Conversión de mensaje a JSON")
        print(f"Origen (mensaje del equipo): {entrada.name}")
        print("Procedencia indicada: registros extraídos desde AWS")
        print(f"Sesiones conservadas: {len(sesiones)}")
        print(f"Sesiones con respuestas: {con_respuestas}")
        print(f"Respuestas conservadas: {total_respuestas}")
        print("Valores y datos originales: sin modificaciones")
        print(f"JSON creado: {salida.resolve()}")
        return 0

    except (ValueError, OSError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
