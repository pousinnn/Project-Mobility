site = "https://www.youtube.com/channel/UClOCC5-WqmdxHZQ5eLldwEQ"
while true
do
echo "monitoring site $site"
sleep 2
xdotool type $site
xdotool key Return

echo "Videos 347" date >> Info.md
sleep 20;
