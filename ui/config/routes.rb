Rails.application.routes.draw do
  root "documents#new"
  resources :documents, only: %i[index create show] do
    member do
      get :html_preview
      post "retry", to: "documents#retry_conversion", as: :retry
    end
  end
  get "up" => "rails/health#show", as: :rails_health_check
end
