---
title: Understanding Models Understanding Nullability
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
header-includes:
  - "<script src=\"sidenotes.js\"></script>"
bibliography: all.bib
linkReferences: true
abstract:

  Large language models have demonstrated impressive emergent
  capabilities, including the ability to write code, but this ability
  requires a model of program semantics that is little
  understood. Recent interpretability work has shown the ability to
  extract internal representations of natural language concepts,
  raising the possibility that similar techniques could be used to
  extract program semantics concepts. In this work we study how large
  language models represent nullability of program values. We measure
  how well models of various sizes complete programs that use nullable
  values, and then extract an internal representation of nullability.

---

# Introduction
The last five years have shown us that Large Language Models can
effectively write programs in many domains.\AT{cite} This is an impressive
capability given that writing programs involves having a working
understanding of many aspects of their semantics. But though we know
that these large models understand programs to an extent, we still
don’t know what form that understanding takes; where it has a deep
understanding and where it uses heuristic reasoning, how it represents
program knowledge, and what kinds of situations will challenge its
capabilities.

Fortunately, recent work in model interpretability and
representation engineering\AT{which work?} has produced promising results
which give hope towards understanding more and more of the
internal thought processes of LLMs. Here at $d_{model}$ , we can
think of no better place to apply these new techniques than
program understanding, where there are many abstract
properties that can be symbolically determined. The vast work
done in programming language theory over the past hundred
years provides many tools for scaling an understanding of the
internal thought processes of language models as they write
code.\AT{for examples, see cite, cite}

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, nullability. Nullable values
are represented differently across languages, null pointers in C++ or
Java, with explicit Option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be nullable is necessary for even
their most basic uses, and misunderstanding where they are nullable
can often be a source of bugs, like a null pointer dereference.

Do our models understand when a value is nullable? They must, to be
able to write code that deals with nullable values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.\todo{big claim!}

In this work, we contribute:

* A microbenchmark of 15 programs that test basic model understanding
  of the flow of nullability through a program ([@sec:bench]).

* We find that models develop an internal concept of
  nullability as they scale up and are trained for longer. ([@sec:probing])

* We find that models begin to understand nullability in a local
  scope, satisfying many requirements of the python typechecker,
  before they start to understand how nullability flows across the
  program. ([@sec:bench], [@sec:results])

# Overview

Understanding the flow of nullability across programs is an essential
part of writing most code, and misunderstandings are often a source of
bugs. For models to write code, they must learn to track nullability
in some form. In this work, we'll explore ways to measure nullability
understanding in language models, and use that to show how the
understanding of nullability changes over various model parameters.

Lets say you're writing a Python program with your LLM assistant. You've
reached some point where you need to do something with a variable
called `num`. Maybe you're building a list of numbers called
`positive_nums`. How do you proceed?

The answer often depends on the context in which you're working. If
`num` and `positive_nums` are the things in scope, then you might
guess that you should write the lines:

```python
if num > 0:
  positive_nums.append(num)
```

And if `num` is always a concrete number, as its name would suggest,
then this is probably the correct code. But variable names don't alway
convey everything important about them, and it might be the case that
`num` could be None. If so, you'll instead want to write:

```python
if num is not None and num > 0:
  positive_nums.append(num)
```

In this case, the way you want to use `num` depends on whether it
could be None or not. That is, whether `num` is "nullable". In Python
that means having an Optional type (`Optional[int]` rather than
`int`).

Determining whether `num` is nullable in this context amounts to *type
inference*, and it can be quite complicated in the worst
case. Fortunately, in many cases it's quite simple, involving applying
just a few rules. For instance, if `num` is the parameter to a
function you're inside, and the function declares the type of `num` in
its parameter list, then you can determine nullability from that
type. So, if your context is:

```python
def foo(num: int):
    positive_nums: list[int] = []
    if num...
```

then you know you don't need to check for None, whereas if it's:

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num...
```

then you know you *do* need a None check.

You could instead just ask your LLM assistant to complete the
line. But how does your assistant know if `num` is nullable? Our
experiments show that LLMs learn to approximate the same typing rules,
by analyzing millions of programs.

If we ask an LLM early in it's pre-training process to complete the
program above, it produces:

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num.is_a():
        ...
```

This is correct Python syntax, but it only works if `num` is an object
with a `is_a()` method, instead of an optional integer.

Train the LLM for a little longer, and it'll produce:

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num > 0:
        ...
```

This is closer, in that its figured out that `num` is a number instead
of an object, but it still isn't reading the function type signature
and realizing that `num` could be None. Keep training it though, and
eventually it will learn to insert the None test depending on the type
signature of the function.

This rule is pretty simple alone, so relatively small models can learn
it, relatively early in their pre-training process. Other, more
complicated rules can take a little longer to learn. For instance, if
your program is:

```python
if condition():
   num = 7
else:
   num = 9
...
if num...
```

then `num` is a non-nullable number, and you can complete the
condition with ` < 0`.

But if instead you're dealing with

```python
if condition():
   num = 7
else:
   num = None
...
if num...
```

Then you'll want a None check first.

This rule takes models a little longer to learn, but your
highly-trained LLM assistant should make quick work of it. Our
experiments show that as these rules get more and more complex, it
takes LLMs longer and longer to learn them, and it also takes LLMs of
more and more parameters to learn them at all.

We can measure whether LLMs understand these rules by just asking for
completions, what we call an "external" measurement of the models
understanding. But there are many places where variables appear where a
completion won't tell you what type the model thinks the variable
has. We would still like to know whether the model thinks these
variables are nullable at those locations, so we can instead look for
an "internal" measurement of the models understanding.

We do so by looking at the activations of the model, meaning the
values of each perceptron in the hidden layers. Together, these values
give the entire internal state of the model at each token, and they
can tell us what the model is "thinking" when processing that
token. With the right tests, we can tell if the model is "thinking"
that the current token is an optional variable, or a non-optional
variable.

By the end of this post, we'll be able to build a probe that uses the
models activations to determine whether the model thinks a variable
read corresponds to a nullable variable, and show that internal
knowledge like so:

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg)

In [@Sec:bench] we'll describe our external tests of nullability
understanding in more detail, and in [@Sec:probing] we'll describe
measuring the models internal states in detail. Finally, we'll go over
some related work in [@Sec:related].

# Measuring Nullability Understanding Externally\AT{Externally = token-level?} {#sec:bench}

We begin by measuring model nullability understanding externally,
because it provides a "skyline" or upper-bound estimate on our ability
to extract internal concepts of nullability. To do this, we have the
model complete simple partial programs that require an understanding
of nullability. We refer to this suite of programs as
`NullabilityEval`. All of the tests in this benchmark suite are
composed of three functions or less, where the largest function is
seven lines long.


We measure the difficulty of these tests by measuring how
models of different sizes perform. We pay particular focus to
the Pythia model suite[@biderman23], as they have checkpoints available across
training runs and various scales. For measuring performance at larger sizes,
we've included Qwen2.5-Coder-32B\AT{cite}, Llama 3.1 405B Instruct\AT{cite}, and
DeepSeek-V3 (671B)\AT{cite}.

Our first test is:

*Test 1*:
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```


The program^[
This partial program is only four lines, with type annotations. A
`some_numbers` array is created that includes positive numbers, negative
numbers, and None values, giving it type `Optional[int]`. A list `result`
is constructed to give the model a sense of dataflow,
and then a loop loops over `some_numbers`.]
is constructed such that there are a very limited number
of valid next lines in the program, and all of them demonstrate some
knowledge of the concept of nullability.^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.
The simplest way to do this is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. Since this is a pretty small space
of valid next lines, and all of them imply some understanding that
`num` may not be an `int`, we can use this program to test models for
nullability understanding by asking them to complete the program
another lines, then see if they produce something that matches these
valid lines with the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

We find that Pythia models as small as 2.8b can successfully complete
this test, and that they learn to complete the test in the first third
of training. Larger Pythia models learn to complete this test earlier,
with Pythia 12b able to complete the test 20% of the way into training
and Pythia 2.8b able to complete it 28% of the way into
training.

## Understanding Typing Rules

How deep is this understanding of nullability? We give a syntax and
semantics of a minimalist subset of python that captures nullability,
and study how well our models perform on each rule.
The full syntax and typing rules of our subset of Python are described
in Appendix [B.1](#sec:commonrules).

With these basic rules, we can construct basic program prefixes that
test the models understanding of nullability.

So, do Pythia models 1.4b and up understand the semantics of all of the
typing rules necessary for this\AT{which} test, or are the confounded by
semiotic information like variable names, whitespace, statement orderings, and
constant values?

For example, while many of the Pythia models
can complete:

```python
some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
result: list[int] = []
for num in some_numbers:
```

with a proper None check, changing the variable names and the
constants into:

```python
foo = [60, None, -33]
bar: list[int] = []
for corejoice in foo:
```

causes all the Pythia models to fail the test. Fortunately,\AT{ideally this is made more concrete, for example by referencing concrete rules or having a plot or table or something}
many simpler typing rules do not exhibit such a strong
reliance on variable naming and constants; in this case, it's the for
loop that causes the model to be confused with certain variable
names. ^[Stay tuned in the future for a more in-depth exploration of how
the models behave on individual typing rules with different contexts
and variable names.]

## Interprocedural Analysis

We can challenge the model more, adding
layers of indirection between the source and sink of nullable values,
and testing the model's _interprocedural_ understanding. Here's one
such test:

*Test 2*
```python
from typing import Optional

def main() -> None:
    some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
    print(positive_numbers(some_numbers))

def positive_numbers(numbers: list[Optional[int]]) -> list[int]:
    result: list[int] = []
    for num in numbers:
```

In this test, we've taken the same logic and spread it across `main`
and another function, `positive_numbers`. Ideally, the model would have
to think a little harder to understand that the `some_numbers` is
flowing through the function call into the body of `positive_numbers`,
causing the for loop body to need a `None` check. In practice though, we
find this test is actually *easier* for the model to pass, with models
as small as Pythia 1b passing it, and Pythia 12b learning to pass it
13% of the way into training.

Because of the type annotations on the
`positive_numbers` function, the model doesn't need to pay attention
to `main` at all. It can just look at `positive_numbers`, and use the
type annotation to know that result contains `Optional[int]`s, so that
since `num` is Nullable, it must be checked for None before proceeding. Looking
at the type annotation turns out to be easier for the model than
scanning through a list to determine if there are None and non-None
values, resulting in an easier test overall.

So how would we *actually* test for interprocedural nullability
understanding in the model? Well, the type annotations on Python
functions aren't required^[Technically this is known as "Optional
typing", but that's confusing in the context of this post. Not to be
confused with Gradual Typing, as introduced by Siek et al.], so we can
instead provide the model with an unannotated function, and see if it
still understands the flow of values from the call site into the
function body. Here's a test that does that:

*Test 3*
```python
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = process_value(value) + 1
    print(x)

def process_value(value):
```

Our base set of typing rules (listed as "Common Rules") don't handle
unannotated functions though, so we're going to have to add some more,
and here we're faced with a choice. The typing rules for normal Python
say that functions without return type annotations return the Any
type, and arguments without a type annotation have the type Any. In
fact, normal mypy will not check unannotated functions at *all*, even
for internal consistency; the `--check-untyped-defs` option will add
some checking back, but the types of arguments and return type will
still be Any. In Python, a value of any type can be converted to an
Any, and an Any can be converted to any value type.

This means that it would be technically type safe to do anything in
the body of `process_value`, including just returning the argument,
without a static type error. But at runtime, code that exploits this
fact would still fail.

If we want code that actually makes sense at runtime, we can
strengthen our type checker a bit, by requiring that there be some
valid (non-Any) type for the function that works at the call site and
in the function body. We still won't be requiring that this type is
actually written down anywhere, but we will be requiring that it
exist. This is called "type inference", when we let the checker pick a
type for us, as long as there is one that works. We'll call this
augmented type system mypy++.\AT{audience should know what type inference is}

In Appendix [B.2](#sec:unannotatedfuncs), we formalize the unannotated
function rules for mypy vs mypy++.

This test is a bit trickier than our previous ones, and we find that
there's no consistent threshold of size at which Pythia models can
pass it. Pythia 1b, 2.8b, and 6.9b pass the test in their final
revisions, but Pythia 410m, 1.4b, and 12b don't. The bigger models all
have points in training where they can pass the test, but only
intermittently. Even 6.9b, the best performing size on this test,
fails the test in its second-to-last available revision^[Despite this,
it does pass the test 40% of the available revisions, about triple
what the other closest sizes can accomplish]. \AT{should we say something about
12b not solving it?}

What the models *can* do well, however, is learn to pass these tests in
the mypy type system (as opposed to mypy++). In that system, where
they don't need to reason globally about the functions but only
locally, this test is one of the easiest for the models to complete.
\AT{perhaps somewhere we should discuss implications for RL}

Since this test suite is meant to be informative beyond the sizes of
the Pythia models, we also add another layer of indirection to add
more difficulty, in this test:

*Test 4*
```python
def handle_value(value, guard):
    if guard:
        return process_value("Foobar") + 1
    else:
        return process_value(value) + 1
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = handle_value(value, x < 10)
    print(x)

def process_value(value):
```

With two layers of indirection, we start to hit the limits of the
capabilities of even frontier models. Llama 405B is unable to
successfully pass this test, as are smaller models like Qwen Coder
32B, while DeepSeek V3 (671B parameters) is able to pass it. However,
Pythia 6.9B is still able to pass this test pretty consistently.

## Generating Type Annotations

Finally, we can test how good the models are at writing their own type
annotations for functions. Since most of the publicly available Python
code is not type-annotated, you could imagine that LLM's can reason
about dataflow correctness without annotations better than they can
write their own typing annotations. The next program tests the models
ability to write its own type annotations; the trailling colon makes
the type expression the only valid completion^[This is because
function declarations with a colon and no type, like `def fn(x:)` are
not valid python. Since we’ve already seen a usage of `get_square`
that is passed a None value, it wouldn’t be type-valid to complete the
program with just `int`. So a model can be tested on its understanding
of `Optional` annotations by seeing if its completion of the partial
program includes `Optional[int]`.]

*Test 5*:
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

None of the Pythia models are able to succesfully pass this test,
demonstrating that writing these annotaions is indeed difficult for
LLM's.\AT{maybe too strong. "indeed more difficult than"?} Qwen Coder 32B is
also incapable of passing this test, but both Llama 405B and DeepSeek V3 pass
it.

## External Test Results Across Training and Scale

We wrote three variations of each of these tests, resulting in 15
tests total. Below, you can see the number of passing tests for each
model.

\todo{more through exploration of why?}

![A bar graph showing how several sizes of model perform on the
 high-level nullability tests](images/hl_model_results.svg){#fig:hl_scale}

In [@Fig:hl_scale], we can see the number of passing tests for each
model. We can see that generally models get better with scale.
\todo{I don't think this footnote is clear enough to add anything}
^[Pythia 12b performs worse than its 6.9b variant, though this might
be due to under-training at that size. Qwen 32B also performs about as
well as Pythia 6.9b, it's not clear if this is due to model
architecture or something else.] Model performance on these tests is
approximately logarithmic in model size: models of 2.8 billion
parameters can pass about half the tests, but it takes more than 405
billion parameters to pass all of the tests. This matches previous
post- and pre-training evaluations of the capabilities of large
language models\todo{cite, Kaplan et al, Chincilla}, indicating that
these tests are well distributed.

![A bar graph showing how the Pythia models perform in mypy vs
 mypy++](images/hl_mypy_vs_grep_models.svg){#fig:hl_mypy}

In [@Fig:hl_mypy], we can see the test result for the pythia models
using the mypy and mypy++ type systems ([@Fig:hl_scale] uses
mypy++). As we expected, the mypy results (red bar) are always above
the mypy++ results (blue bar), as mypy++ is a stricter type
system. There are six tests in the dataset involving non-annotated
functions, and using the weaker mypy typesystem causes up to five more
tests to pass than using mypy++^[We don't see all six non-annotated
function tests passing under mypy, because models can still fail these
tests by producing invalid syntax.]

Next, we want to understand the training dynamics at play here. Below
we can see how Pythia 6.9b performs on the tests during training from
step 2 to 143000:\todo{let's use the same axes scaling at the tigges
paper}

![A line graph showing how the performance of the Pythia
6.9 model changes during training](images/hl_revision_results.svg){#fig:hl_time}

Again, performance does not increase monotonically.  This plot is
quite noisy, so in the sequel, we will show smoothed^[rolling average
with a window size of 5] charts.

In the graph below, we see that each individual model also learns to
write code which typechecks under mypy before it learns to write code
which typechecks under mypy++ and throws no type errors at runtime.

![A graph showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that shows true
understanding.](images/hl_mypy_vs_grep_revisions.svg){#fig:hl_moral}

# Measuring Nullability Understanding Internally {#sec:probing}

At this point, we’ve figured out how to roughly measure nullability
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. In this section, we detail how we train reading vectors
[@sec:extraction], using prompts designed to make the model think about
the phenomena of interest [@sec:prompts]. Finally [@sec:results], we validate that
these probes improve their understanding of nullability over the course
of pretraining to the level that we expect from the external, or token-level
understanding evals we describe in the previous section.

## Background

<!--
As language models predict each token in a text, they run their tuned
circuits over all the previous text. Tokens are first embedded into a
high-dimensional "token space", and each layer of the transformer
model is made up of many parallel circuits which transform the
previous layers output into new embeddings in a new space. Each layer
can look not just at the output of the layer directly previous, but
actually all previous layers, through a channel called a residual
stream.

The paper presents two main approaches to interpreting a language
model; circuit-based, and representation-based. Circuit based
interpretability aims to pair down the network to a key set of
circuits which are sufficient to complete a particular task; this
allows practitioners to point to a particular part of the model and
say "this is where \<task\> is done", much like neuroscientists assign
functionality to different parts of our brain.

-->

In this section, we review representation engineering [@zou25] techniques that
we will use to look for linear representations of nullability inside the model.

@zou25 shows how representations can be extracted for
concepts like "happiness", "honesty", and "fairness". First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with "Pretend you’re a dishonest person. The Eiffel Tower is" and
"Pretend you’re an honest person. The Eiffel Tower is". Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is activated in the model during any given forward pass (e.g. for honesty,
this gives us a lie-detector).

![Figure from @zou25  showing the reading outputs for several
 concepts](images/zhou.png)

## Designing Prompts to Extract Nullability Activations {#sec:prompts}

We avoid dealing with the ambiguities of natural language by working in
a setting where the model needs only to complete code. analyze the nullability
of individual variable occurrences. Specifically, we probe for "the variable
I just generated refers to an nullable quantity", so our prompts looked like:

```python
def program_1() -> None:
  def find_value(data: List[int], target: int) -> Optional[int]:
    for value in data:
      if value == target:
      return value
    return None

  data = [1, 2, 3, 4, 5]
  target = 3
  result = find_value(data, target)
  if result
```

We queried o1, o1-mini, deepseek-coder, and claude-3.5-sonnet with the following prompt:

> Generate me 100 typed python programs that use the Optional type,
> along with type annotations for any undefined functions that they
> use. Make sure that the programs are unique, and each involves at
> least eight lines of logic. Number each program from 1 to 100. Please
> put all the programs in a single file, with a main function that tests
> each. Don't include any text before or after the code, just the
> code. I will be using mypy with the --strict option to check the code.

We label each variable read occurrence with nullability information derived
from mypy, and prompt the "model under test" with a prompt consisting of the
tokens up to and including the variable read occurrence.

## Extracting Reading Vectors {#sec:extraction}

\AT{Overall, I'm not really sure what our takeaway is for this section. I think we want the reader to understand that we did some experiements with mass mean probing and the various normalization mehtods, but I'm not sure we're making any compelling point here beyond "we ran the experiment". I think we can appendicize the latter two plots --- they look pretty noisy, and I'm not sure they're acutally something to draw conclusions from}

We use Mass Mean Shift probing which
has been shown empirically [@li24] to generalize better in high dimensional
spaces than logistic
regression.^[see "Mass Mean Probing vs Linear
Regression" in the appendix]

In the reading vector, the impact of each layer is based on the
magnitude of mean difference in that layer.
w we decided to try a few different methods of normalizing
these layers to improve their overall accuracy as a linear model:

The reading vectors from each layer are the mean difference in activations
between when the feature (nullability) is present or not. This leaves open
the question of how to weight the reading vectors from different layers.
We evaluate the follow cross-layer normalization schemes:

* No normalization; just summing over the average differences
* Normalizing each layers vector to a uniform length
* Dividing by the average amount that each layer activates on the positive samples
* Dividing by the average absolute amount that each layer activates on the positive samples
* Dividing by the square root of the average of squares of layer activations
\AT{ add some theory for this}
\AT{ include a results table }
\AT{ add equations. these words are so hard to read.}

We find that "no normalization" performs the best.

\todo{ this is ... sort of... a contribution?}
Prior work focused their probing on a single layer, often handpicked
based on prior papers. In our experiments, we decided to probe *all*
layers using a mass means probe, and learn which ones were most
important from the data. We tested two methods for doing so - either
allowing the magnitude of the difference of means vector to determine
the importance of the layer in the final probe, or to learn
coefficients for each layer using linear regression. We found that
which method is more accurate on test data varies over both model size
and number of training steps.

![The performance of pure mass means probing vs mass means probing
 with linear regression for different Pythia model sizes. Binary-cross
 entropy is plotted, so lower is
 better.](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.
\AT{not really sure these plots are saying what we're saying they're saying}

![The performance of the two probing methods on the Pythia 160m model
 for different numbers of pretraining steps. There are regions where
 pure mass means scaling is better, and regions where linear
 regression on layer weights is better.](images/mm-vs-mmlr-160m.svg){#fig:mm-vs-mmlr-160m}

In [@Fig:mm-vs-mmlr-160m;@Fig:mm-vs-mmlr-410], we look at how these
scaling methods perform for different amounts of pretraining, for the
model sizes nearest the boundary. We see that relative merit of each
scaling method can vary significantly over pretraining steps.

![The performance of the two probing methods on the Pythia 410m model
for different numbers of pretraining steps. Pure mass means probing
starts better, but is quickly overtaken by mass means probing with
linear regression on layer weights.](images/mm-vs-mmlr-410m.svg){#fig:mm-vs-mmlr-410}

## Probing Results Across Training and Scale {#sec:results}

In this section, we study the performance of our nullability probes across time
and scale [@tigges24].
We use mass-means shift probing [@li24] on all layers,
and a linear regression to determine the weights of each layer.^[
@li24 and @zou25 suggest that mass means probes are best for reading,
while the direction perpendicular to the separating hyperplane is best for
intervention.
However, previous work leaves open the question of cross-layer weights. We use
LR on the cross-layer weights, thanks to our investigations above.]
\AT{see appendix D for mm vs LR}

![The performance, measured in binary cross-entropy, of each Pythia
 model size during pretraining. Since this graph is of loss, lower is
 better](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@Fig:models-and-steps], we plot loss against scale and time.
While we
measured accuracy for every available Pythia model size, we exclude
the smallest (14m) from this plot since it would
exist entirely above the top of the plot.
We notice turning points in the models' understanding of nullability at 1b parameters and \todo{number of tokens}.
We explore the texture of these in \todo{future work}.

## Visualizing Probe Outputs

Now that we've shown how to train these probes with increasing
accuracy, lets bring back the reading diagram we showed in the intro,
and go a bit more into depth with it.

We adapted this style of reading diagram from @zou25, but only show
the activations on tokens that represent variable loads, since that is
where we trained our probe^[There is also a much more practical
reason: right after the model has generated a variable that will be
written to, it often does not have access to the assigning expression
or type annotation, giving it no way to determine if the value will be
optional or now.]. For each measured token, we're running the model
until just after that token, then extracting it's hidden state and
measuring probe activation. We then color the box above that token
depending on the activations, and the scoring threshold inferred at
train-time^[Red tokens are significantly below the threshold, and
green tokens are significantly above it; tokens that scored near the
threshold would have a near-white color, but no such tokens appear in
this example.].

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg)

We can see here sixteen tokens that correspond to variable reads in
the program, and all but one are probed as non-optional
(correctly). The only nullable variable in this program is `result`,
since it comes from `find_value` which returns `Optional[int]`. So
when this variable appears for the first time in the `if` statement
checking if it's none, the model knows it is nullable, and the results
of the probe reflect that understanding. But when it appears a second
time on the next line, in the format string of `print`, the model no
longer thinks it is optional, since the body of this if statement only
runs if it is *not* `None`; the probe accurately reflects this.

# Related Work {#sec:related}

Our decision to use Pythia to study feature evolution across time and scale is
inspired by @tigges24 . They focus on classic circuits-centered
interpretability tasks such as IOI, Gendered-Pronoun, Greater-Than, and SVA \AT{cite}.

In our setting, we are more interested in representation-centered
interpretability looks at how activations vary across inputs, to extract
representations of particular concepts. @zou25 surveys techniques for
representation engineering with linear probes. We apply similar techniques, but
to program semantics and dataflow instead of natural language.

@feng24predicate also study LLM's ability to reason about propositions, but in
a natural language setting, rather than a formal one.

Several techniques exist for constructing linear probes, but after
experimental measurement we followed the mass means shift from @li24. @li24
and @zhong23 discuss why mass mean probing might outperform linear regression.

# Future Work

\AT{Typing rules staircase plot}

# References {.unnumbered}
::: {#refs}
:::
