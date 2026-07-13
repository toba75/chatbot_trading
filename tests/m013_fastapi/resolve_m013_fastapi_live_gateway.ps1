function Resolve-M013FastApiLiveGatewayUrl {
    if ([string]::IsNullOrWhiteSpace($env:M013_FASTAPI_LLM_GATEWAY_URL)) {
        throw "M013_FASTAPI_LLM_GATEWAY_URL_REQUIRED: exécuter cette preuve via la gate Live."
    }
    try {
        $uri = [System.Uri]::new($env:M013_FASTAPI_LLM_GATEWAY_URL)
    }
    catch [System.UriFormatException] {
        throw "M013_FASTAPI_LLM_GATEWAY_URL_INVALID"
    }
    if (
        -not $uri.IsAbsoluteUri -or
        $uri.Scheme -ne "http" -or
        $uri.Host -ne "127.0.0.1" -or
        $uri.Port -lt 1 -or
        $uri.AbsolutePath -ne "/" -or
        -not [string]::IsNullOrEmpty($uri.Query) -or
        -not [string]::IsNullOrEmpty($uri.Fragment)
    ) {
        throw "M013_FASTAPI_LLM_GATEWAY_URL_INVALID"
    }
    return $uri.GetLeftPart([System.UriPartial]::Authority)
}
