#encoding: UTF-8
require 'rubygems'
require 'haml'
require 'open-uri'
require 'digest/md5'
require 'json'

require 'sinatra'
require 'date'

disable :run

# What could possibly go wrong?
def read_json_file(path)
  JSON.parse(File.open(path){ |f| f.read })
end

# That's right our database is the file system.
module Model
  # Reverse chronological
  MEETUPS = read_json_file('data/meetups.json').sort{ |a,b|
            b["num"] <=> a["num"] }
  PURPOSE = read_json_file('data/purpose.json')
  LINKS   = read_json_file('data/links.json')

  MENU=[
    { :label => "About",
      :href => "about",
      :section => "about"},
    { :label => "Where is it?",
      :href => "map",
      :section => "map"},
    { :label => "Be a presenter",
      :href => "present",
      :section => "present"},
    { :label => "Archive",
      :href => 'archive',
      :section => 'archive'}]

  # SITE = {
  #   :index      => { :label => "Current", :href => "/", :cls => "current" },
  #   :archive    => { :label => "Archive", :href => "archive" },
  #   :directions => { :label => "Where is it?", :href => "map" },
  #   :present    => { :label => "Want to present?", :href => "present" },
  #   :about      => { :label => "About", :href => "about" }
  # }
end

helpers do

  # Returns the URL for the gravatar image associated with the email
  def gravaturl(email)
    hash = Digest::MD5.hexdigest(email.downcase)
    "http://www.gravatar.com/avatar/#{hash}"
  end

  # Builds the top menu like a boss.
  def menu(current)
    Model::MENU.map{ |m|
      li_class =
      [current == m[:section] ? "active" : "", m[:cls].to_s].join(" ")
      "<li class=\"#{li_class}\"><a href=\"#{m[:href]}\">#{m[:label]}</a>"
    }.join("")
  end

  # Is this meetup happening in the past?
  def past?(meetup)
    Date.parse(meetup["on"]) < Date.today
  end

  # Do we have enough speakers for the next meetup (ie, more than 1)
  # If not we're gonna change the header a bit..
  def booked?
    meetup = Model::MEETUPS.first
    meetup["speakers"].size > 1
  end

  def gogodate( yyyymmdd )
    "#{yyyymmdd[0..3]}.#{yyyymmdd[4..5]}.#{yyyymmdd[6..7]}"
  end

  def zedate(meetup)
    Date.parse(meetup["on"]).strftime("%A, %B %d")
  end
end

before do
  # We're gonna need those
  @links = Model::LINKS
end


get "/meetups/*.json" do |index|
  content_type :json

  body = (if index == "current"
    Model::MEETUPS.first
  else
    meetup = Model::MEETUPS.detect{|m| m["num"] == index.to_i}
    meetup ||= {}
  end).to_json
end


get "/meetups/*.html" do |index|
  content_type :html

  meetup = Model::MEETUPS.detect{|m| m["num"] == index.to_i}
  haml :_meetup_mobile, :layout => false,
       :locals => { :meetup => meetup }

end


get "/meetups.json" do
  content_type :json
  body Model::MEETUPS.to_json
end

get "/css/mobile.css" do
  sass :mobile
end

get "/meetups/current/?" do
  # Exclude the current meeting
  haml :_meetup_mobile, :layout => false,
       :locals => { :meetup => Model::MEETUPS.first }
end


get "/archive/?" do
  @section = "previously"

  # Exclude the current meeting
  haml :meetups, :locals => { :meetups => Model::MEETUPS.reject{
    |m| m == Model::MEETUPS.first }}
end

get "/?" do
  @section = "index"
  haml :index, :locals => { :meetup => Model::MEETUPS.first }
end

get "/about/?" do
  @section = "about"
  haml :about, :locals => { :purpose => Model::PURPOSE }
end

get "/present/?" do
  @section = "present"
  haml :present, :locals => { :purpose => Model::PURPOSE }
end

get "/mobile/?" do
  haml :mobile, :layout => false
end

# Return the contents of the Yahoo Pipe
# The pipe contains good shit.  It is displayed in the rainbow.
get "/data/js-links" do
  content_type :json
  expires (60*60*24), :public, :must_revalidate
  begin
    pipe = "_id=8ddf68d81456be270ea845566f3698b2&_render=json"
    pipe_content =
      open("http://pipes.yahoo.com/pipes/pipe.run?#{pipe}").read
    body JSON.generate(JSON.parse(pipe_content)["value"]["items"])
  rescue
    body "[]"
  end
end

get "/map/?" do
  @section = "map"
  haml :map
end

# Configuration
set :app_file, __FILE__
set :root, File.dirname(__FILE__)
set :public, Proc.new { File.join( root, "public") }

