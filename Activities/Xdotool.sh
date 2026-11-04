
#!/bin/bash

site="https://www.youtube.com/channel/UClOCC5-WqmdxHZQ5eLldwEQ"

while true
do
    echo "Monitoring site: $site"

    # Esperar antes de abrir el sitio
    sleep 2

    # Seleccionar la barra de direcciones
    xdotool key ctrl+l

    # Escribir la URL
    xdotool type --clearmodifiers "$site"

    # Presionar Enter
    xdotool key Return

    # Registrar información y fecha
    echo "Videos 347 - $(date)" >> Info.md

    # Esperar 20 segundos antes de repetir
    sleep 20
done
