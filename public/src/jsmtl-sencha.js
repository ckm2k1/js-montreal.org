// JS-MONTREAL.ORG
// Sencha Touch mobile version


(function(){


// Ext.Application

// Sets up an application object that creates a bunch of
// namespaces: jsmtl.views, jsmtl.controllers, etc...
// Triggers the 'launch' event after launching.

new Ext.Application({
  name   : 'jsmtl',
  launch : function() {
    this.viewport = new Ext.TabPanel(mainView);
  }
});



// Models & Stores
// ---------------
// Sencha has a sophisticated model & data store component -
// complete with relationships, persistence, etc.  It is
// quite sophisticated and there's enough material in it for
// a 10 hour seminar.

// A very, very simple example of a model for the historical meetups

Ext.regModel('Talk', {

// The name of a the property that is a unique identifier

  idProperty  : 'num',

// Fields. Type default to strings.

  fields      : ['num', 'title', 'on']

});


var mainView = {

// Will get applied to the main container for the application
// The cls key is a regular css class that Sencha adds when
// building the widgets

  cls: 'mobile',

// Take up the entire screen when rendering the component

  fullscreen: true,

// The 'defaults' member is special
// it basically gets applied to all children
// configuration defined in the 'items' member

  defaults: {

  },

// The items collection is where you define the
// children of a component. Internally it is stored
// as a MixedCollection, which is essentially a custom
// collection object.

  items: [{

    xtype   : 'panel',

// Sencha ships with a ton of icons

    iconCls : 'star',
    title   : 'Current',
    scroll  : 'vertical',

    styleHtmlContent: true

  },{

    iconCls : 'search',
    title   : 'Previous',
    layout  : 'card',

// Easy to add some effect pizzazz

    cardSwitchAnimation: 'flip',

    items   : [{

// The first panel is the list of previous meetups

      xtype   : 'list',
      itemTpl : '<span class="date">{on}</span> {title}',
      singleSelect: true,

      store   : new Ext.data.Store({

        model     : 'Talk',

// Can't figure out why your data isn't loading? You probably
// forgot autoLoad

        autoLoad  : true,
        proxy : {
          type   : 'ajax',
          url    : '/meetups.json',
          reader : {
            type : 'json'
          }
        }
      })

    },{

      scroll  : 'vertical',
      styleHtmlContent: true,

      dockedItems: [{

        dock  : 'top',
        xtype : 'toolbar',
        title : 'Previous meetup',
        items  : [{

          id      : 'backbutton',
          itemCls : 'back',
          text    : 'Back'

        }]
      }]
    }]

  },{
    iconCls: 'locate',
    title: 'Where',
    items: {
      xtype: 'map',
      title: 'Cakemail',
      useCurrentLocation: true,
      mapOptions: {
        zoom: 10
      }
    }
  }],

  tabBar: {
    dock: 'bottom',
    layout: {
      pack: 'center'
    }
  }
};


jsmtl.on('launch', function(app){


  var viewportItems = app.viewport.items,

// The first item in the viewport items collection is the
// the 'current' view, showing the current meetup

      current = viewportItems.getAt(0),

// The second item in the viewport is the history panel

      history = viewportItems.getAt(1),

// which contains a list of all the previous meetups

      list = history.items.getAt(0),

// and a (hidden at first) panel where the detail of a specific
// meetup is going to go

      historyPanel = history.items.getAt(1),

// A mask to show while we're loading the data for the current meetup

      currentMask = new Ext.LoadMask( current.getEl(),
                                    { msg: "Loading..." });


// When we click an item in the list of previous meetup,
// load up the markup for that meetup and display it in a
// panel

  list.on('selectionchange', function(model, records){

    if (records.length > 0){

      var data = records[0].data;

      console.debug(data);


// Load the HTML markup for the selected meetup using ajax
// and update the second panel of the history tab

      Ext.Ajax.request({
        url: '/meetups/' + data.num + '.html',

        callback: function(options, success, response){

          historyPanel.update(response.responseText);
          history.setActiveItem(1);
        }
      });
    }
  });

// Load the markup for the current meetup
// and update the current view

// First mask the view while the request is happening
  currentMask.show();

  Ext.Ajax.request({

// This route returns html markup

    url: '/meetups/current',

    callback: function(options, success, response){
      current.update(response.responseText);
      currentMask.hide();
    }

  });

// You can always find a component by Id if you must
// Here, the back button we've defined in the historical
// meetup view


  var backbutton = Ext.getCmp('backbutton');

  backbutton.on('tap', function(){

    list.deselect( list.getSelectedRecords() );
    history.setActiveItem(0);

  });



});


})();