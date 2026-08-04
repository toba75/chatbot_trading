# Pin npm packages by running ./bin/importmap

pin "application"
pin "@hotwired/turbo-rails", to: "turbo.min.js"
pin "@hotwired/stimulus", to: "stimulus.min.js"
pin "@hotwired/stimulus-loading", to: "stimulus-loading.js"
# PDF.js 6.1.200, copié depuis le paquet npm officiel pdfjs-dist.
pin "pdfjs-dist", to: "pdfjs/pdf.min.js"
pin_all_from "app/javascript/controllers", under: "controllers"
