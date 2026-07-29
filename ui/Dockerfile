FROM ruby:4.0.6-slim@sha256:abd7528c4df35d151e2643d5efb845e442a26e36a4babc6459bee508619137a2

ENV LANG=C.UTF-8 \
    BUNDLE_PATH=/usr/local/bundle \
    BUNDLE_JOBS=4 \
    BUNDLE_RETRY=3

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       build-essential \
       chromium \
       chromium-driver \
       curl \
       libpq-dev \
       postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY Gemfile Gemfile.lock ./
RUN bundle install

COPY . .

EXPOSE 3000

CMD ["bundle", "exec", "rails", "server", "--binding=0.0.0.0"]
