const { src, dest, watch, series } = require("gulp");
const sass = require("gulp-sass")(require("sass"));
const autoprefixer = require("gulp-autoprefixer").default; // <-- THIS FIX
const cleanCSS = require("gulp-clean-css");
const browserSync = require("browser-sync").create();

// Sass Task (Compile SCSS + Autoprefix + Minify)
function scssTask() {
  return src("./assets/scss/*.scss")
    .pipe(sass().on("error", sass.logError))
    .pipe(autoprefixer({ cascade: false }))
    .pipe(cleanCSS({ compatibility: "ie11" }))
    .pipe(dest("./assets/css/"))
    .pipe(browserSync.stream());
}

// BrowserSync Server Task
function browserSyncServer(cb) {
  browserSync.init({
    server: {
      baseDir: ".",
    },
    notify: false,
    open: false
  });
  cb();
}

// BrowserSync Reload Task
function browserSyncReload(cb) {
  browserSync.reload();
  cb();
}

// Watch Task
function watchTask() {
  watch(["*.html", "./assets/js/**/*.js"], browserSyncReload);
  watch(["./assets/scss/**/*.scss"], scssTask);
}

// Default Gulp Task
exports.default = series(scssTask, browserSyncServer, watchTask);
