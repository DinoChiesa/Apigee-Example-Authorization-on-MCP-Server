FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY / /app

RUN adduser --disabled-password --gecos "" myuser && chown -R myuser:myuser /app
USER myuser

ENV PATH="/home/myuser/.local/bin:$PATH"
# When executing this container image manually, one can 
# override the default port with -e "PORT=8088" on the docker command line. 
# eg, podman run -e "PORT=5555"  my_image
#
ENV PORT 8080

# Cloud Run will do that implicitly.

#CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
CMD ["sh", "-c", "python main.py --port $PORT"]


