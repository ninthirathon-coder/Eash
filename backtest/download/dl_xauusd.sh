get() { # $1=path-suffix $2=date $3=datemonth $4=out
  U="https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/xauusd/$1"
  curl -sS -m 60 -c cj.txt -b cj.txt "$U" -o p.html
  TK=$(grep -oE 'name="tk" id="tk" value="[^"]*"' p.html | head -1 | sed 's/.*value="//;s/"//')
  curl -sS -m 300 -b cj.txt -c cj.txt -e "$U" -X POST https://www.histdata.com/get.php \
    -d "tk=$TK&date=$2&datemonth=$3&platform=ASCII&timeframe=M1&fxpair=XAUUSD" -o "raw/$4.zip"
  echo "$4 $(stat -c%s raw/$4.zip)"
}
for y in 2009 2010 2011 2012 2013 2014 2015; do get $y $y $y $y; sleep 2; done
