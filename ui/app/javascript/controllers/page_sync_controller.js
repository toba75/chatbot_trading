import { Controller } from "@hotwired/stimulus"
import * as pdfjsLib from "pdfjs-dist"

export default class extends Controller {
  static targets = ["canvas", "viewer", "page", "total", "previous", "next", "status", "htmlTab", "correctedHtmlTab", "nativeHtmlTab", "jsonTab", "doclingPreview", "htmlSyncNotice"]
  static values = { pdfUrl: String, htmlUrl: String, htmlSynchronized: Boolean, jsonUrl: String, pageCount: Number, workerUrl: String }

  async connect() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = this.workerUrlValue
    this.currentPage = 1
    this.renderVersion = 0
    this.loadingTask = pdfjsLib.getDocument({ url: this.pdfUrlValue })

    try {
      this.pdf = await this.loadingTask.promise
      if (this.pdf.numPages !== this.pageCountValue) {
        this.incompatiblePageCounts = true
        this.pageTarget.disabled = true
        this.previousTarget.disabled = true
        this.nextTarget.disabled = true
        this.showError("Le PDF original et la conversion Docling n’ont pas le même nombre de pages.")
        return
      }
      this.pageTarget.max = this.pdf.numPages
      this.totalTarget.textContent = this.pdf.numPages
      const requestedPage = Number.parseInt(this.pageTarget.value, 10)
      const initialPage = this.pendingPage || requestedPage || 1
      this.pendingPage = null
      await this.showPage(initialPage)
    } catch (error) {
      this.showError("Le PDF original n’a pas pu être affiché.")
      console.error(error)
    }
  }

  disconnect() {
    this.renderTask?.cancel()
    this.loadingTask?.destroy()
  }

  previous() {
    this.showPage(this.currentPage - 1)
  }

  next() {
    this.showPage(this.currentPage + 1)
  }

  choosePage(event) {
    this.showPage(Number.parseInt(event.currentTarget.value, 10))
  }

  selectJson(event) {
    this.selectPreview(event, this.jsonUrl(this.currentPage))
  }

  selectHtml(event) {
    this.selectPreview(event, this.htmlUrl(event.currentTarget, this.currentPage))
  }

  useHtmlUrl(event) {
    this.htmlUrlValue = event.detail.url
    this.htmlSynchronizedValue = true
    const tab = event.detail.corrected ? this.correctedHtmlTabTarget : this.nativeHtmlTabTarget
    tab.hidden = false
    tab.dataset.pageSyncBaseUrl = event.detail.url
    tab.dataset.pageSyncSynchronized = "true"
    tab.dataset.pageSyncTitle = event.detail.label
    tab.textContent = event.detail.label
    if (this.hasHtmlSyncNoticeTarget) this.htmlSyncNoticeTarget.hidden = true
    this.updateHtmlTab(tab)
    this.updateHtmlPreview()
  }

  async showPage(requestedPage) {
    if (this.incompatiblePageCounts || !Number.isInteger(requestedPage)) return
    if (!this.pdf) {
      this.pendingPage = requestedPage
      return
    }

    const pageNumber = Math.min(Math.max(requestedPage, 1), this.pdf.numPages)
    const version = ++this.renderVersion
    this.renderTask?.cancel()
    this.pageTarget.value = this.currentPage
    this.statusTarget.textContent = `Chargement de la page ${pageNumber}…`
    this.statusTarget.hidden = false

    try {
      const page = await this.pdf.getPage(pageNumber)
      if (version !== this.renderVersion) return

      const initialViewport = page.getViewport({ scale: 1 })
      const scale = Math.max((this.viewerTarget.clientWidth - 32) / initialViewport.width, 0.25)
      const viewport = page.getViewport({ scale })
      const pixelRatio = window.devicePixelRatio || 1
      const stagedCanvas = document.createElement("canvas")
      stagedCanvas.width = Math.floor(viewport.width * pixelRatio)
      stagedCanvas.height = Math.floor(viewport.height * pixelRatio)
      this.renderTask = page.render({
        canvasContext: stagedCanvas.getContext("2d"),
        viewport,
        transform: pixelRatio === 1 ? null : [pixelRatio, 0, 0, pixelRatio, 0, 0]
      })
      await this.renderTask.promise
      if (version !== this.renderVersion) return

      const canvas = this.canvasTarget
      canvas.width = stagedCanvas.width
      canvas.height = stagedCanvas.height
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`
      canvas.getContext("2d").drawImage(stagedCanvas, 0, 0)
      canvas.dataset.renderedPage = pageNumber
      this.currentPage = pageNumber
      this.statusTarget.hidden = true
      this.updateNavigation()
      this.updateHtmlPreview()
      this.updateJsonPreview()
    } catch (error) {
      if (error?.name === "RenderingCancelledException") return
      if (version === this.renderVersion) this.showError(`La page ${pageNumber} n’a pas pu être affichée.`)
      console.error(error)
    }
  }

  updateNavigation() {
    this.pageTarget.value = this.currentPage
    this.previousTarget.disabled = this.currentPage === 1
    this.nextTarget.disabled = this.currentPage === this.pdf.numPages
    this.htmlTabTargets.forEach(tab => this.updateHtmlTab(tab))
    this.jsonTabTarget.href = this.jsonUrl(this.currentPage)
    this.jsonTabTarget.dataset.previewTitle = `Projection JSON de la page ${this.currentPage}`
  }

  updateHtmlPreview() {
    const tab = this.htmlTabTargets.find(candidate => candidate.getAttribute("aria-selected") === "true")
    if (tab) {
      this.doclingPreviewTarget.src = this.htmlUrl(tab, this.currentPage)
      this.doclingPreviewTarget.title = tab.dataset.previewTitle
    }
  }

  updateJsonPreview() {
    if (this.jsonTabTarget.getAttribute("aria-selected") === "true") {
      this.doclingPreviewTarget.src = this.jsonUrl(this.currentPage)
      this.doclingPreviewTarget.title = this.jsonTabTarget.dataset.previewTitle
    }
  }

  jsonUrl(page) {
    const url = new URL(this.jsonUrlValue, window.location.origin)
    url.searchParams.set("page", page)
    return `${url.pathname}${url.search}`
  }

  updateHtmlTab(tab) {
    tab.href = this.htmlUrl(tab, this.currentPage)
    tab.dataset.previewTitle = this.htmlTitle(tab, this.currentPage)
  }

  htmlUrl(tab, page) {
    const baseUrl = tab.dataset.pageSyncBaseUrl
    return tab.dataset.pageSyncSynchronized === "true" ? `${baseUrl}#page-${page}` : baseUrl
  }

  htmlTitle(tab, page) {
    const title = tab.dataset.pageSyncTitle
    return tab.dataset.pageSyncSynchronized === "true" ? `${title} — page ${page}` : title
  }

  selectPreview(event, url) {
    event.preventDefault()
    event.currentTarget.href = url
    this.doclingPreviewTarget.src = url
    this.doclingPreviewTarget.title = event.currentTarget.dataset.previewTitle
  }

  showError(message) {
    this.statusTarget.textContent = message
    this.statusTarget.hidden = false
  }
}
