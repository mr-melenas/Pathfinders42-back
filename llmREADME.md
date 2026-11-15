# Ejecutar el LLM localmente con Ollama

Esta guía configura el backend para usar Ollama en el mismo ordenador. Las peticiones se envían a
`localhost`; no hace falta crear una cuenta de Ollama ni configurar una clave API.

## 1. Instalar Ollama

Descarga el instalador para tu sistema desde la [página oficial de descargas de Ollama](https://ollama.com/download):

- **Windows:** descarga y ejecuta el instalador. Al terminar, abre Ollama desde el menú Inicio y vuelve a abrir PowerShell.
- **macOS:** descarga Ollama y mueve la aplicación a `Applications`; después, ábrela.
- **Linux:** sigue las instrucciones de la página oficial. La instalación indicada por Ollama es:

  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

Comprueba que el comando está disponible:

```powershell
ollama --version
```

En Windows y macOS, Ollama mantiene el servidor local al abrir la aplicación. En Linux, si el servidor no
está iniciado automáticamente, ejecuta `ollama serve` en una terminal y déjala abierta.

## 2. Descargar y probar el modelo local

El modelo predeterminado del proyecto es **Gemma 4 E2B** (`gemma4:e2b`), una variante pequeña que Ollama
ejecuta localmente sin cuenta ni clave API. La descarga ocupa aproximadamente **5–7,5 GB** según la
cuantización; Ollama recomienda unos **8 GB de VRAM o memoria unificada**.

```powershell
ollama pull gemma4:e2b
ollama list
ollama run gemma4:e2b "Responde solo: OK"
```

La ejecución local no envía peticiones a la API de pago en la nube. El uso de CPU/RAM/GPU depende del
ordenador y puede afectar a la velocidad.

## 3. Configurar el backend

Desde la carpeta `Pathfinders42-back`, crea `.env` a partir del ejemplo si todavía no existe:

```powershell
Copy-Item .env.example .env
```

En `.env`, deja estos valores para usar Ollama localmente:

```dotenv
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=
MODEL_LLM=gemma4:e2b
LLM_DISABLE_THINKING=0
```

La clave se deja vacía para el servidor local. `LLM_DISABLE_THINKING=0` evita enviar opciones específicas de
otros servidores compatibles con OpenAI. No guardes claves reales en `.env.example` ni las subas al repositorio.

## 4. Verificar la API local

Con Ollama abierto, ejecuta esta prueba en PowerShell:

```powershell
$body = @{
    model = "gemma4:e2b"
    messages = @(@{ role = "user"; content = "Responde solo: OK" })
    stream = $false
} | ConvertTo-Json -Depth 5

$response = Invoke-RestMethod `
    -Uri "http://localhost:11434/v1/chat/completions" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response.choices[0].message.content
```

La respuesta debe incluir `OK`. Ollama documenta esta ruta como compatible con OpenAI:
[`/v1/chat/completions`](https://docs.ollama.com/api/openai-compatibility#simple-v1chatcompletions-example).

## 5. Arrancar la API del proyecto

Instala las dependencias y arranca el backend desde `Pathfinders42-back`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn --env-file .env app.main:app --reload
```

La documentación de la API estará en <http://localhost:8000/docs>. El servidor del modelo de Ollama debe
seguir ejecutándose en segundo plano mientras se usa el backend.

## Reproducibilidad

Anota la versión de Ollama (`ollama --version`) y el modelo exacto (`ollama list`) junto con los resultados.
El nombre de `MODEL_LLM` debe coincidir con el modelo descargado.

## Referencias oficiales

- [Descargar Ollama](https://ollama.com/download)
- [Inicio rápido de Ollama](https://docs.ollama.com/quickstart)
- [Compatibilidad de Ollama con la API de OpenAI](https://docs.ollama.com/api/openai-compatibility)
- [Modelos Gemma 4 disponibles en Ollama](https://ollama.com/library/gemma4)