// JS-MONTREAL
// Sencha Touch mobile version


// GOTCHAS so far
// 1. the rendering sequence
// 'fullscreen' renders the component immediately!  don't use that
// unless that's what you need


(function(){



//var mainView = {

var mainView = {
  id: 'mainPanel',
  fullscreen: true,
  cls: 'mobile',

  items: [{
    ui: 'dark',
    iconCls: 'favorites',
    title: 'Currently',
    html: 'Currently'
  },{
    iconCls: 'favorites',
    title: 'Previously',
    html: 'bbq'
  },{
    iconCls: 'default',
    title: 'Where',
    items: {
      xtype: 'map',
      useCurrentLocation: true
    }
  },{
    iconCls: 'default',
    title: 'About',
    html: 'About JS-MONTREAL'
  }],

  tabBar: {
    dock: 'bottom',
    scroll: {
      direction: 'horizontal',
      useIndicators: true
    },
    layout: {
      pack: 'center'
    }
  }
};

var jsmtl = new Ext.Application({
    name: 'jsmtl',

    launch: function() {
      this.viewport = new Ext.TabPanel(mainView);
    }
});



})();