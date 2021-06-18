FROM gorialis/discord.py:3.9-alpine-minimal

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]