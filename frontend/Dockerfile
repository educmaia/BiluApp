# Usa a imagem oficial do Nginx como base
FROM nginx:alpine

# Remove a configuração padrão do Nginx para evitar conflitos
RUN rm /etc/nginx/conf.d/default.conf

# Copia o seu ficheiro de configuração personalizado, que agora está na mesma pasta,
# para o local correto dentro da imagem.
COPY nginx.conf /etc/nginx/conf.d/

# O Nginx irá carregar automaticamente qualquer ficheiro .conf desta pasta ao iniciar.
