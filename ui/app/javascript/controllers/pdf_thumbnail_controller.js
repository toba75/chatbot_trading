import { Controller } from "@hotwired/stimulus"
import * as pdfjsLib from "pdfjs-dist"

export default class extends Controller {
  static targets = ["canvas", "status"]
  static values = { pdfUrl: String, workerUrl: String }

  async connect() {
    pdfjsLib.GlobalWorkerOptions.workerSrc = this.workerUrlValue
    this.loadingTask = pdfjsLib.getDocument({ url: this.pdfUrlValue })

    try {
      const pdf = await this.loadingTask.promise
      const page = await pdf.getPage(1)
      const initialViewport = page.getViewport({ scale: 1 })
      const availableWidth = this.element.clientWidth || 160
      const scale = Math.min(availableWidth / initialViewport.width, 1)
      const viewport = page.getViewport({ scale })
      const pixelRatio = window.devicePixelRatio || 1
      const canvas = this.canvasTarget
      canvas.width = Math.floor(viewport.width * pixelRatio)
      canvas.height = Math.floor(viewport.height * pixelRatio)
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`

      this.renderTask = page.render({
        canvasContext: canvas.getContext("2d"),
        viewport,
        transform: pixelRatio === 1 ? null : [pixelRatio, 0, 0, pixelRatio, 0, 0]
      })
      await this.renderTask.promise
      this.statusTarget.hidden = true
    } catch (error) {
      this.statusTarget.textContent = "La miniature du PDF n’a pas pu être affichée."
      console.error(error)
    }
  }

  disconnect() {
    this.renderTask?.cancel()
    this.loadingTask?.destroy()
  }
}
