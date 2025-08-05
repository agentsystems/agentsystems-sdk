# Lightweight backup side-car
FROM alpine:3.20

# Install dependencies: rclone and PostgreSQL client
RUN apk add --no-cache rclone postgresql-client bash curl tzdata

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV BACKUP_SCHEDULE="3600"
CMD ["/entrypoint.sh"]
