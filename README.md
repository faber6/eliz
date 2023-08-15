# eliz
discord chatbot that integrates with this [enma-api](https://github.com/faber6/enma-api) fork, based on [eliza](https://github.com/harubaru/eliza) and [shimeji](https://github.com/hitomi-team/shimeji)

## Installations
0. Virtual env
```
python3 -m venv venv && source venv/bin/activate
```

1. Install requirements:
```
pip install -r requirements.txt
```

2. Edit config or start.sh (.env config will be prioritized)

3. Run
```
python main.py
```
or
```
chmod +x ./start.sh && ./start.sh
```