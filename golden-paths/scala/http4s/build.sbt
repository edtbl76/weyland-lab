ThisBuild / scalaVersion := "3.3.4"

name := "golden-scala-http4s"

val http4sVersion = "0.23.28"

libraryDependencies ++= Seq(
  "org.http4s" %% "http4s-ember-server" % http4sVersion,
  "org.http4s" %% "http4s-dsl" % http4sVersion,
  "io.prometheus" % "simpleclient" % "0.16.0",
  "io.prometheus" % "simpleclient_common" % "0.16.0",
  "ch.qos.logback" % "logback-classic" % "1.5.6" % Runtime,
  "org.scalameta" %% "munit" % "1.0.2" % Test,
  "org.typelevel" %% "munit-cats-effect" % "2.0.0" % Test
)

enablePlugins(JavaAppPackaging)

Compile / mainClass := Some("golden.Main")

// The deliberate-fail test lives in a *Deliberate* class; a normal run excludes it and the lane
// self-check (`sbt -Dselfcheck=true test`) runs ONLY it. Name-based, but fail-closed: dropping the
// "Deliberate" marker makes it run in the NORMAL lane, which is loud, not silent.
Test / testOptions := Seq(Tests.Filter { name =>
  if (sys.props.get("selfcheck").contains("true")) name.contains("Deliberate")
  else !name.contains("Deliberate")
})
