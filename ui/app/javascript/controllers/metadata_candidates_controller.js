import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["card", "input"]

  connect() {
    this.refresh()
  }

  toggle(event) {
    const card = event.target.closest('[data-metadata-candidates-target~="card"]')
    if (!card || !this.element.contains(card)) return

    const input = this.inputTargets.find(candidate => candidate.closest('[data-metadata-candidates-target~="card"]') === card)
    if (!input) return

    const wasSelected = this.selectedInput === input
    const nativeActivation = event.target.matches('input[type="radio"]') || event.target.closest("label")
    if (!wasSelected && nativeActivation) return

    if (wasSelected) {
      event.preventDefault()
      if (event.target.closest("label")) input.focus()
      setTimeout(() => {
        if (this.selectedInput !== input) return
        input.checked = false
        this.refresh()
      }, 0)
      return
    }

    this.inputTargets.forEach(candidate => { candidate.checked = false })
    input.checked = true
    this.refresh()
  }

  refresh() {
    this.selectedInput = null
    this.cardTargets.forEach(card => {
      const input = card.querySelector('input[type="radio"]')
      const selected = input?.checked === true
      if (selected) this.selectedInput = input
      card.classList.toggle("is-selected", selected)
    })
  }
}
