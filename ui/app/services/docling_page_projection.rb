require "oj"

class DoclingPageProjection
  COLLECTIONS = %w[texts pictures tables key_value_items form_items].freeze
  METADATA = %w[schema_name version name origin].freeze

  class PageNotFound < StandardError
    attr_reader :page

    def initialize(page)
      @page = page
      super("La page #{page} est absente du DoclingDocument.")
    end
  end

  Frame = Data.define(:type, :key, :value, :capture_root)

  def self.call(io, page:, math_links: [])
    new(page, math_links).tap { |projection| projection.parse(io) }.result
  end

  attr_reader :result

  def initialize(page, math_links)
    @page = page
    @stack = []
    @result = {
      "_projection" => {
        "kind" => "docling_page",
        "page_no" => page,
        "selection" => "contenus dont prov.page_no correspond à la page",
        "excluded_top_level_keys" => %w[furniture body groups]
      },
      "_math_links" => math_links,
      "page" => nil
    }
    COLLECTIONS.each { |collection| @result[collection] = [] }
  end

  def parse(io)
    parser = Oj::Parser.new(:saj)
    parser.handler = self
    parser.load(io)
    raise PageNotFound, @page unless @result["page"]
  end

  def hash_start(key, *)
    start_container(Hash, key)
  end

  def array_start(key, *)
    start_container(Array, key)
  end

  def hash_end(_key, *)
    finish_container
  end

  def array_end(_key, *)
    finish_container
  end

  def add_value(value, key, *)
    if capturing?
      attach(@stack.last.value, key, value)
    elsif @stack.one? && METADATA.include?(key)
      @result[key] = value
    end
  end

  private

  def start_container(type, key)
    if capturing?
      value = type.new
      attach(@stack.last.value, key, value)
      @stack << Frame.new(type, key, value, false)
    elsif capture_root?(key)
      @stack << Frame.new(type, key, type.new, true)
    else
      @stack << Frame.new(type, key, nil, false)
    end
  end

  def capture_root?(key)
    return METADATA.include?(key) if @stack.one?
    return false unless @stack.length == 2

    parent = @stack.last
    (parent.type == Array && COLLECTIONS.include?(parent.key)) ||
      (parent.type == Hash && parent.key == "pages" && key.to_i == @page)
  end

  def capturing?
    !@stack.empty? && !@stack.last.value.nil?
  end

  def attach(parent, key, value)
    parent.is_a?(Array) ? parent << value : parent[key] = value
  end

  def finish_container
    frame = @stack.pop
    return unless frame.capture_root

    parent_key = @stack.last&.key
    if parent_key == "pages"
      @result["page"] = frame.value
    elsif COLLECTIONS.include?(parent_key) && attributed_to_page?(frame.value)
      @result[parent_key] << frame.value
    elsif METADATA.include?(frame.key)
      @result[frame.key] = frame.value
    end
  end

  def attributed_to_page?(item)
    item.fetch("prov", []).any? { |provenance| provenance["page_no"] == @page }
  end
end
